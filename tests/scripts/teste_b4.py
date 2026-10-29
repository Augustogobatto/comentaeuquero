"""Teste do B4: webhook -> gatilho -> runtime.

Monta payloads no formato que a Meta manda e verifica o caminho inteiro, do POST
do webhook até a mensagem que teria saído. Instagram dublado, nada sai pra Meta.
"""
import os
import shutil
import sys

DATA = "/tmp/ceq_b4"
shutil.rmtree(DATA, ignore_errors=True)
os.makedirs(DATA)
os.environ["DATA_DIR"] = DATA
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import db, flowengine, instagram, runtime  # noqa: E402

ENVIADOS, PUBLICAS = [], []
falhas = []


def _fake(kind):
    def f(account, recipient, *a, **kw):
        ENVIADOS.append({"kind": kind, "recipient": recipient, "args": a})
        return True, 200, "ok"
    return f


instagram.send_text = _fake("text")
instagram.send_buttons = _fake("buttons")
instagram.send_quick_replies = _fake("quick_replies")
instagram.send_media = _fake("media")
instagram.fetch_profile = lambda *a, **kw: {}


def fake_public(account, comment_id, text):
    PUBLICAS.append({"comment_id": comment_id, "text": text})
    return True, 200, "ok"


instagram.send_public_reply = fake_public
runtime.THROTTLE_S = 0


def check(nome, cond, detalhe=""):
    print(f"  {'OK ' if cond else 'FALHOU'}  {nome}{'  ' + detalhe if detalhe else ''}")
    if not cond:
        falhas.append(nome)


db.init()
conta = db.upsert_account("IGACC", "17841000", "augustogobatto", "tok",
                          db.in_seconds_iso(86400 * 60))

# fluxo A: keyword "aurora", qualquer post, com resposta pública
fa = db.create_flow(conta["id"], "aurora", entry_node="n1", graph={
    "nodes": [{"id": "n1", "type": "text", "data": {"text": "oi {username}, aqui é a Aurora"}}],
    "edges": []})
db.add_trigger(fa, "comment", ["aurora"], public_reply="te mandei no direct ✅")
db.add_trigger(fa, "story_reply", ["aurora"])
db.add_trigger(fa, "dm", ["aurora"])

# fluxo B: keyword "dente", SÓ no post MEDIA_X
fb = db.create_flow(conta["id"], "dente", entry_node="n1", graph={
    "nodes": [{"id": "n1", "type": "text", "data": {"text": "fluxo do post especifico"}}],
    "edges": []})
db.add_trigger(fb, "comment", ["dente"], media_ids=["MEDIA_X"])

# fluxo C: só comentário em live
fc = db.create_flow(conta["id"], "live", entry_node="n1", graph={
    "nodes": [{"id": "n1", "type": "text", "data": {"text": "vim da live"}}],
    "edges": []})
db.add_trigger(fc, "live_comment", ["quero"])

# fluxo D: botões, pra testar postback e quick reply
fd = db.create_flow(conta["id"], "escolha", entry_node="n1", graph={
    "nodes": [{"id": "n1", "type": "buttons", "data": {"text": "escolhe", "buttons": [
        {"title": "A", "key": "opa"}, {"title": "B", "key": "opb"}]}},
        {"id": "n2", "type": "text", "data": {"text": "foi A"}},
        {"id": "n3", "type": "text", "data": {"text": "foi B"}}],
    "edges": [{"source": "n1", "target": "n2", "sourceHandle": "opa"},
              {"source": "n1", "target": "n3", "sourceHandle": "opb"}]})
db.add_trigger(fd, "dm", ["escolha"])


def comentario(texto, media="MEDIA_QUALQUER", cid="c1", user="fulana", uid="U1", live=False):
    return {"entry": [{"id": "IGACC", "changes": [{
        "field": "live_comments" if live else "comments",
        "value": {"id": cid, "text": texto, "media": {"id": media},
                  "from": {"id": uid, "username": user}}}]}]}


def mensagem(texto, mid="m1", uid="U1", story=False):
    msg = {"mid": mid, "text": texto}
    if story:
        msg["reply_to"] = {"story": {"id": "s1"}}
    return {"entry": [{"id": "IGACC", "messaging": [
        {"sender": {"id": uid}, "recipient": {"id": "IGACC"}, "message": msg}]}]}


print("\n[1] comentário com a palavra-chave dispara o fluxo")
ENVIADOS.clear(); PUBLICAS.clear()
flowengine.process_payload(comentario("eu quero a AURORA!", cid="c1", uid="U1"))
check("mandou a DM", len(ENVIADOS) == 1, f"{len(ENVIADOS)}")
check("foi por private reply", ENVIADOS[0]["recipient"] == {"comment_id": "c1"})
check("renderizou o username", "fulana" in ENVIADOS[0]["args"][0], ENVIADOS[0]["args"][0])
check("respondeu no comentário", len(PUBLICAS) == 1 and PUBLICAS[0]["comment_id"] == "c1")

print("\n[2] comentário sem a palavra-chave não dispara")
ENVIADOS.clear()
flowengine.process_payload(comentario("que post lindo", cid="c2", uid="U2"))
check("ficou quieto", len(ENVIADOS) == 0, f"{len(ENVIADOS)}")

print("\n[3] palavra dentro de outra palavra não dispara")
ENVIADOS.clear()
flowengine.process_payload(comentario("boreal auroral", cid="c3", uid="U3"))
check("'auroral' não aciona 'aurora'", len(ENVIADOS) == 0, f"{len(ENVIADOS)}")

print("\n[3b] plural aciona a palavra-chave no singular")
ENVIADOS.clear()
flowengine.process_payload(comentario("auroras boreais", cid="c3b", uid="U3b"))
check("'auroras' aciona 'aurora'", len(ENVIADOS) == 1, f"{len(ENVIADOS)}")

print("\n[4] acento e caixa não atrapalham")
ENVIADOS.clear()
flowengine.process_payload(comentario("AurOrA", cid="c4", uid="U4"))
check("casou mesmo com caixa trocada", len(ENVIADOS) == 1)

print("\n[5] reentrega do mesmo comentário não responde de novo")
ENVIADOS.clear()
flowengine.process_payload(comentario("aurora", cid="c1", uid="U1"))
check("dedupe segurou", len(ENVIADOS) == 0, f"{len(ENVIADOS)}")

print("\n[6] post específico: só dispara no post certo")
ENVIADOS.clear()
flowengine.process_payload(comentario("dente", media="OUTRO_POST", cid="c6", uid="U6"))
check("no post errado, nada", len(ENVIADOS) == 0, f"{len(ENVIADOS)}")
flowengine.process_payload(comentario("dente", media="MEDIA_X", cid="c7", uid="U7"))
check("no post certo, dispara", len(ENVIADOS) == 1)
check("é o fluxo do post", "post especifico" in ENVIADOS[-1]["args"][0])

print("\n[7] comentário em live usa o gatilho de live")
ENVIADOS.clear()
flowengine.process_payload(comentario("quero", cid="c8", uid="U8", live=True))
check("disparou pelo live_comment", len(ENVIADOS) == 1)
check("é o fluxo da live", ENVIADOS[-1]["args"][0] == "vim da live", ENVIADOS[-1]["args"][0])
ENVIADOS.clear()
flowengine.process_payload(comentario("quero", cid="c9", uid="U9", live=False))
check("mesmo texto em post normal não dispara o fluxo da live", len(ENVIADOS) == 0)

print("\n[8] resposta de story e DM")
ENVIADOS.clear()
flowengine.process_payload(mensagem("aurora", mid="m1", uid="U10", story=True))
check("story reply dispara", len(ENVIADOS) == 1)
check("vai por igsid", ENVIADOS[0]["recipient"] == {"id": "U10"})
ENVIADOS.clear()
flowengine.process_payload(mensagem("aurora", mid="m2", uid="U11"))
check("DM dispara", len(ENVIADOS) == 1)

print("\n[9] eco e mensagem da própria conta são ignorados")
ENVIADOS.clear()
eco = {"entry": [{"id": "IGACC", "messaging": [
    {"sender": {"id": "IGACC"}, "message": {"mid": "m3", "text": "aurora", "is_echo": True}}]}]}
flowengine.process_payload(eco)
check("eco ignorado", len(ENVIADOS) == 0)
flowengine.process_payload(comentario("aurora", cid="c10", uid="IGACC"))
check("comentário da própria conta ignorado", len(ENVIADOS) == 0)

print("\n[10] clique em botão retoma pelo ramo certo")
ENVIADOS.clear()
flowengine.process_payload(mensagem("escolha", mid="m4", uid="U12"))
check("fluxo de botões começou", len(ENVIADOS) == 1 and ENVIADOS[0]["kind"] == "buttons")
postback = {"entry": [{"id": "IGACC", "messaging": [
    {"sender": {"id": "U12"}, "postback": {"mid": "pb1", "payload": "opb", "title": "B"}}]}]}
flowengine.process_payload(postback)
check("seguiu o ramo B", ENVIADOS[-1]["args"][0] == "foi B", ENVIADOS[-1]["args"][0])

print("\n[11] quick reply também retoma")
ENVIADOS.clear()
flowengine.process_payload(mensagem("escolha", mid="m5", uid="U13"))
qr = {"entry": [{"id": "IGACC", "messaging": [
    {"sender": {"id": "U13"}, "message": {"mid": "m6", "text": "A",
                                          "quick_reply": {"payload": "opa"}}}]}]}
flowengine.process_payload(qr)
check("seguiu o ramo A", ENVIADOS[-1]["args"][0] == "foi A", ENVIADOS[-1]["args"][0])

print("\n[12] quem está esperando resposta não recomeça por keyword")
ENVIADOS.clear()
fe = db.create_flow(conta["id"], "captura", entry_node="n1", graph={
    "nodes": [{"id": "n1", "type": "wait_input", "data": {"expects": "texto",
                                                          "save_as": "cidade"}},
              {"id": "n2", "type": "text", "data": {"text": "anotei {cidade}"}}],
    "edges": [{"source": "n1", "target": "n2"}]})
db.add_trigger(fe, "dm", ["cidade"])
flowengine.process_payload(mensagem("cidade", mid="m7", uid="U14"))
lead14 = db.touch_lead(conta["id"], "U14")
check("está esperando texto",
      db.active_session_for_lead(lead14["id"])["waiting_for"] == "text")
# agora responde com uma palavra que TAMBÉM é keyword de outro fluxo
flowengine.process_payload(mensagem("aurora", mid="m8", uid="U14"))
check("tratou como resposta, não como novo gatilho",
      db.get_field(lead14["id"], "cidade") == "aurora",
      db.get_field(lead14["id"], "cidade"))
check("seguiu o fluxo da captura", ENVIADOS[-1]["args"][0] == "anotei aurora",
      ENVIADOS[-1]["args"][0])

print("\n[13] fluxo desativado não dispara")
ENVIADOS.clear()
db.update_flow(fa, active=0)
flowengine.process_payload(comentario("aurora", cid="c11", uid="U15"))
check("fluxo off fica quieto", len(ENVIADOS) == 0, f"{len(ENVIADOS)}")
db.update_flow(fa, active=1)

print("\n[14] webhook de conta desconhecida não quebra")
ENVIADOS.clear()
flowengine.process_payload({"entry": [{"id": "OUTRA_CONTA", "changes": [
    {"field": "comments", "value": {"id": "cx", "text": "aurora",
                                    "from": {"id": "U99", "username": "x"}}}]}]})
check("ignorou sem estourar", len(ENVIADOS) == 0)

print("\n" + ("TUDO PASSOU" if not falhas else f"FALHAS ({len(falhas)}): {falhas}"))
sys.exit(1 if falhas else 0)
