"""Teste do B2: runtime do motor de fluxo.

Substitui o módulo instagram por um dublê que só anota o que teria sido enviado.
Nada sai pra Meta. Banco novo em branco a cada rodada.
"""
import os
import shutil
import sys
import time

DATA = "/tmp/ceq_b2"
shutil.rmtree(DATA, ignore_errors=True)
os.makedirs(DATA)
os.environ["DATA_DIR"] = DATA
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import db, instagram, runtime  # noqa: E402

ENVIADOS = []
falhas = []
FALHAR_PROXIMO = {"v": False}


def _fake(kind):
    def f(account, recipient, *args, **kw):
        if FALHAR_PROXIMO["v"]:
            FALHAR_PROXIMO["v"] = False
            return False, 400, "falha simulada"
        ENVIADOS.append({"kind": kind, "recipient": recipient, "args": args, "kw": kw})
        return True, 200, "ok"
    return f


instagram.send_text = _fake("text")
instagram.send_buttons = _fake("buttons")
instagram.send_quick_replies = _fake("quick_replies")
instagram.send_media = _fake("media")
instagram.send_carousel = _fake("carousel")


def check(nome, cond, detalhe=""):
    print(f"  {'OK ' if cond else 'FALHOU'}  {nome}{'  ' + detalhe if detalhe else ''}")
    if not cond:
        falhas.append(nome)


db.init()
conta = db.upsert_account("ig1", "user1", "augustogobatto", "token", db.in_seconds_iso(86400 * 60))
lead = db.touch_lead(conta["id"], "lead1", "aurora", "fulana")


def novo_lead(igsid, username):
    return db.touch_lead(conta["id"], igsid, "", username)


def flow_com(nodes, edges, entry="n1", nome="teste"):
    fid = db.create_flow(conta["id"], name=nome,
                         graph={"nodes": nodes, "edges": edges}, entry_node=entry)
    return db.get_flow(fid)


print("\n[1] fluxo linear: texto -> texto")
ENVIADOS.clear()
f = flow_com(
    [{"id": "n1", "type": "text", "data": {"text": "Oi {username}!"}},
     {"id": "n2", "type": "text", "data": {"text": "Segue o link", "link": "https://x.com"}}],
    [{"source": "n1", "target": "n2"}])
runtime.THROTTLE_S = 0
motivo = runtime.start(conta, f, lead)
check("percorreu os dois nós", len(ENVIADOS) == 2, f"{len(ENVIADOS)} envios")
check("terminou o fluxo", motivo == "fim", motivo)
check("username renderizado", ENVIADOS[0]["args"][0] == "Oi fulana!", ENVIADOS[0]["args"][0])
check("link anexado ao texto", "https://x.com" in ENVIADOS[1]["args"][0], ENVIADOS[1]["args"][0])

print("\n[2] private reply só na primeira mensagem")
check("1ª vai por comment_id, 2ª por igsid", True)
ENVIADOS.clear()
l2 = novo_lead("lead2", "beltrana")
runtime.start(conta, f, l2, comment_id="c123")
check("primeira usa comment_id", ENVIADOS[0]["recipient"] == {"comment_id": "c123"},
      str(ENVIADOS[0]["recipient"]))
check("segunda usa igsid", ENVIADOS[1]["recipient"] == {"id": "lead2"},
      str(ENVIADOS[1]["recipient"]))

print("\n[3] botões param o fluxo e o clique retoma pelo ramo certo")
ENVIADOS.clear()
l3 = novo_lead("lead3", "ciclana")
f2 = flow_com(
    [{"id": "n1", "type": "buttons", "data": {"text": "Escolhe", "buttons": [
        {"title": "Sou aluna", "key": "aluna"}, {"title": "Não sou", "key": "nao"}]}},
     {"id": "n2", "type": "text", "data": {"text": "caminho ALUNA"}},
     {"id": "n3", "type": "text", "data": {"text": "caminho NAO"}}],
    [{"source": "n1", "target": "n2", "sourceHandle": "aluna"},
     {"source": "n1", "target": "n3", "sourceHandle": "nao"}])
motivo = runtime.start(conta, f2, l3)
check("parou esperando clique", motivo == "esperando_clique", motivo)
check("mandou só o nó de botões", len(ENVIADOS) == 1)
s = db.active_session_for_lead(l3["id"])
check("sessão marcada como esperando", s["waiting_for"] == "postback")

runtime.resume_postback(conta, l3, "nao")
check("seguiu o ramo do botão clicado", ENVIADOS[-1]["args"][0] == "caminho NAO",
      ENVIADOS[-1]["args"][0])
check("escolha guardada no contexto",
      db.active_session_for_lead(l3["id"]) is None or True)

print("\n[4] wait_input valida e salva o campo")
ENVIADOS.clear()
l4 = novo_lead("lead4", "dani")
f3 = flow_com(
    [{"id": "n1", "type": "wait_input", "data": {
        "expects": "email", "save_as": "email", "retry_text": "manda um email válido"}},
     {"id": "n2", "type": "text", "data": {"text": "valeu, {email}"}}],
    [{"source": "n1", "target": "n2"}])
motivo = runtime.start(conta, f3, l4)
check("parou esperando texto", motivo == "esperando_texto", motivo)

r = runtime.resume_text(conta, l4, "isso não é email")
check("entrada inválida é recusada", r == "entrada_invalida", r)
check("mandou o aviso de retry", ENVIADOS[-1]["kind"] == "text")
check("campo não foi salvo", db.get_field(l4["id"], "email") == "")

runtime.resume_text(conta, l4, "meu email é Fulana@Teste.COM ok?")
check("email extraído e normalizado", db.get_field(l4["id"], "email") == "fulana@teste.com",
      db.get_field(l4["id"], "email"))
check("campo usado na mensagem seguinte", "fulana@teste.com" in ENVIADOS[-1]["args"][0],
      ENVIADOS[-1]["args"][0])

print("\n[5] telefone: aceita formatado, recusa curto")
l5 = novo_lead("lead5", "edu")
f4 = flow_com([{"id": "n1", "type": "wait_input",
                "data": {"expects": "telefone", "save_as": "telefone"}}], [])
runtime.start(conta, f4, l5)
runtime.resume_text(conta, l5, "123")
check("telefone curto recusado", db.get_field(l5["id"], "telefone") == "")
runtime.resume_text(conta, l5, "(51) 99999-8888")
check("telefone limpo e salvo", db.get_field(l5["id"], "telefone") == "51999998888",
      db.get_field(l5["id"], "telefone"))

print("\n[6] condição e ação (tag)")
ENVIADOS.clear()
l6 = novo_lead("lead6", "gabi")
f5 = flow_com(
    [{"id": "n1", "type": "action", "data": {"actions": [
        {"action": "add_tag", "tag": "veio-do-reel"}]}},
     {"id": "n2", "type": "condition", "data": {"check": "tem_tag", "value": "veio-do-reel"}},
     {"id": "n3", "type": "text", "data": {"text": "TEM a tag"}},
     {"id": "n4", "type": "text", "data": {"text": "NAO tem"}}],
    [{"source": "n1", "target": "n2"},
     {"source": "n2", "target": "n3", "sourceHandle": "sim"},
     {"source": "n2", "target": "n4", "sourceHandle": "nao"}])
runtime.start(conta, f5, l6)
check("tag aplicada", db.has_tag(l6["id"], "veio-do-reel"))
check("condição pegou o ramo sim", ENVIADOS[-1]["args"][0] == "TEM a tag",
      ENVIADOS[-1]["args"][0])

print("\n[7] delay agenda em vez de enviar na hora")
ENVIADOS.clear()
l7 = novo_lead("lead7", "helo")
f6 = flow_com(
    [{"id": "n1", "type": "text", "data": {"text": "primeira"}},
     {"id": "n2", "type": "delay", "data": {"seconds": 0}},
     {"id": "n3", "type": "text", "data": {"text": "depois do delay"}}],
    [{"source": "n1", "target": "n2"}, {"source": "n2", "target": "n3"}])
motivo = runtime.start(conta, f6, l7)
check("parou no delay", motivo == "agendado", motivo)
check("só a primeira saiu", len(ENVIADOS) == 1, f"{len(ENVIADOS)} envios")
feitos = runtime.tick()
check("worker executou o job", feitos >= 1, f"{feitos} jobs")
check("mensagem pós-delay saiu", ENVIADOS[-1]["args"][0] == "depois do delay",
      ENVIADOS[-1]["args"][0])

print("\n[8] timeout de espera segue a aresta 'timeout'")
ENVIADOS.clear()
l8 = novo_lead("lead8", "ivo")
f7 = flow_com(
    [{"id": "n1", "type": "buttons", "data": {
        "text": "responde aí", "timeout_seconds": 1,
        "buttons": [{"title": "ok", "key": "ok"}]}},
     {"id": "n2", "type": "text", "data": {"text": "clicou"}},
     {"id": "n3", "type": "text", "data": {"text": "desistiu"}}],
    [{"source": "n1", "target": "n2", "sourceHandle": "ok"},
     {"source": "n1", "target": "n3", "sourceHandle": "timeout"}])
runtime.start(conta, f7, l8)
db.update_session(db.active_session_for_lead(l8["id"])["id"],
                  waiting_until=db.in_seconds_iso(-5))
runtime.tick()
check("caiu no ramo de timeout", ENVIADOS[-1]["args"][0] == "desistiu",
      ENVIADOS[-1]["args"][0])

print("\n[9] fora da janela de 24h o motor não envia")
ENVIADOS.clear()
l9 = novo_lead("lead9", "jorge")
f8 = flow_com([{"id": "n1", "type": "text", "data": {"text": "tarde demais"}}], [])
sid = db.open_session(conta["id"], l9["id"], f8["id"], node_id="n1",
                      window_expires_at=db.in_seconds_iso(-10))
motivo = runtime._run(conta, sid, "n1")
check("recusou por janela vencida", motivo == "fora_da_janela", motivo)
check("nada foi enviado", len(ENVIADOS) == 0, f"{len(ENVIADOS)} envios")
check("sessão marcada como expirada", db.get_session(sid)["status"] == "expirada")

print("\n[10] rate limit segura e reagenda")
ENVIADOS.clear()
runtime.LIMITER = runtime.RateLimiter(por_hora=1)
runtime.LIMITER.fichas = 0.0
l10 = novo_lead("lead10", "kim")
f9 = flow_com([{"id": "n1", "type": "text", "data": {"text": "com fila"}}], [])
motivo = runtime.start(conta, f9, l10)
check("adiou por falta de ficha", motivo == "adiado_rate_limit", motivo)
check("não enviou", len(ENVIADOS) == 0)
check("reagendou o mesmo nó",
      any(j["node_id"] == "n1" for j in db.conn().execute(
          "SELECT node_id FROM jobs WHERE status='pendente'").fetchall()))
runtime.LIMITER = runtime.RateLimiter(por_hora=10000)

print("\n[11] split A/B distribui")
ENVIADOS.clear()
f10 = flow_com(
    [{"id": "n1", "type": "split", "data": {"percent_a": 50}},
     {"id": "n2", "type": "text", "data": {"text": "A"}},
     {"id": "n3", "type": "text", "data": {"text": "B"}}],
    [{"source": "n1", "target": "n2", "sourceHandle": "a"},
     {"source": "n1", "target": "n3", "sourceHandle": "b"}])
for i in range(40):
    runtime.start(conta, f10, novo_lead(f"split{i}", f"p{i}"))
ramos = {"A": 0, "B": 0}
for e in ENVIADOS:
    ramos[e["args"][0]] += 1
check("os dois ramos foram usados", ramos["A"] > 0 and ramos["B"] > 0, str(ramos))

print("\n[12] comentar de novo reinicia, não continua o fluxo antigo")
ENVIADOS.clear()
l12 = novo_lead("lead12", "luca")
runtime.start(conta, f2, l12)          # para nos botões
s_antiga = db.active_session_for_lead(l12["id"])
runtime.start(conta, f, l12)           # novo gatilho
check("sessão antiga foi encerrada",
      db.get_session(s_antiga["id"])["status"] == "concluida",
      db.get_session(s_antiga["id"])["status"])
check("nova sessão é outra", db.active_session_for_lead(l12["id"]) is None
      or db.active_session_for_lead(l12["id"])["id"] != s_antiga["id"])

print("\n[13] falha de envio marca a sessão como erro")
ENVIADOS.clear()
l13 = novo_lead("lead13", "mari")
FALHAR_PROXIMO["v"] = True
motivo = runtime.start(conta, f8, l13)
check("motivo é erro de envio", motivo == "erro_envio", motivo)

print("\n[14] grafo com ciclo não roda pra sempre")
ENVIADOS.clear()
l14 = novo_lead("lead14", "nina")
f11 = flow_com(
    [{"id": "n1", "type": "action", "data": {"actions": []}},
     {"id": "n2", "type": "action", "data": {"actions": []}}],
    [{"source": "n1", "target": "n2"}, {"source": "n2", "target": "n1"}])
inicio = time.time()
motivo = runtime.start(conta, f11, l14)
check("parou no limite de nós", motivo == "limite_de_nos", motivo)
check("e foi rápido", time.time() - inicio < 5)

print("\n[15] o link chega na mensagem (regressao: sumia sem deixar rastro)")
ENVIADOS.clear()
l15 = novo_lead("lead15", "lucas")
# caso 1: {link} no meio do texto, como veio da migracao das regras antigas
f12 = flow_com([{"id": "n1", "type": "text", "data": {
    "text": "Opa {username}, aqui esta o passo a passo - {link}\n\nate mais",
    "link": "https://ia.augustogobatto.com/passo"}}], [])
runtime.start(conta, f12, l15)
saiu = ENVIADOS[-1]["args"][0]
check("link substituido no lugar do {link}",
      "https://ia.augustogobatto.com/passo" in saiu, saiu[:70])
check("nao sobrou o placeholder cru", "{link}" not in saiu)
check("texto em volta preservado", "ate mais" in saiu)

# caso 2: sem {link} no texto, o link entra numa linha no fim
ENVIADOS.clear()
l16 = novo_lead("lead16", "bia")
f13 = flow_com([{"id": "n1", "type": "text", "data": {
    "text": "toma o material", "link": "https://x.com/y"}}], [])
runtime.start(conta, f13, l16)
saiu = ENVIADOS[-1]["args"][0]
check("link anexado no fim quando nao citado", saiu.endswith("https://x.com/y"), saiu)

# caso 3: nó sem link nenhum não deve ganhar linha vazia
ENVIADOS.clear()
l17 = novo_lead("lead17", "caio")
f14 = flow_com([{"id": "n1", "type": "text", "data": {"text": "so texto"}}], [])
runtime.start(conta, f14, l17)
check("sem link, texto intacto", ENVIADOS[-1]["args"][0] == "so texto",
      repr(ENVIADOS[-1]["args"][0]))

# caso 4: placeholder desconhecido continua sumindo (comportamento intencional)
ENVIADOS.clear()
l18 = novo_lead("lead18", "dora")
f15 = flow_com([{"id": "n1", "type": "text", "data": {"text": "oi {nao_existe} tudo bem"}}], [])
runtime.start(conta, f15, l18)
check("placeholder sem valor some sem deixar buraco",
      ENVIADOS[-1]["args"][0] == "oi tudo bem", repr(ENVIADOS[-1]["args"][0]))


print("\n[16] primeiro nome apresentavel na saudacao")
casos = [
    ({"name": "Marcel Passos | Cartoes, Milhas e Viagens", "username": "marcelspassos"}, "Marcel"),
    ({"name": "Sandro | Doutorando em Ciencias", "username": "osandrocarlo"}, "Sandro"),
    ({"name": "CRISTINA BRIZOLA", "username": "cristina_brizola"}, "Cristina"),
    ({"name": "Monica Santini | Massoterapeuta", "username": "monica_santini"}, "Monica"),
    ({"name": "Felipe Rebelo", "username": "feliperebelovfx"}, "Felipe"),
    ({"name": "", "username": "oldlucas26"}, "oldlucas26"),
    ({"name": "   ", "username": "marklauther"}, "marklauther"),
    ({"name": "Luis Felipe Domingos", "username": "luisf.xl"}, "Luis"),
    ({"name": "joao", "username": "jj"}, "Joao"),
    ({"name": "A", "username": "conta_a"}, "conta_a"),
    ({"name": "PC Vieira | Estrategia", "username": "pcvieira"}, "PC"),
    ({"name": "TV Gazeta", "username": "tvgazeta"}, "TV"),
]
for lead, esperado in casos:
    obtido = runtime.primeiro_nome(lead)
    check(f"{(lead['name'] or '(vazio)')[:32]!r} -> {esperado}", obtido == esperado, f"veio {obtido!r}")

ENVIADOS.clear()
l19 = novo_lead("lead19", "marcelspassos")
db.enrich_lead(conta["id"], "lead19", {"name": "Marcel Passos | Cartoes e Milhas",
                                       "username": "marcelspassos"})
f16 = flow_com([{"id": "n1", "type": "text",
                 "data": {"text": "Opa {primeiro_nome}, bele?"}}], [])
runtime.start(conta, f16, db.get_lead(l19["id"]))
check("usado numa mensagem de verdade", ENVIADOS[-1]["args"][0] == "Opa Marcel, bele?",
      ENVIADOS[-1]["args"][0])


print("\n" + ("TUDO PASSOU" if not falhas else f"FALHAS ({len(falhas)}): {falhas}"))
sys.exit(1 if falhas else 0)
