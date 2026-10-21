"""Testa o gate de seguidor: condição e_seguidor com reconsulta ao vivo.

O cenário que motivou o patch: a pessoa comenta sem seguir, o fluxo pede pra
seguir, ela segue e clica em "já estou seguindo". Sem a reconsulta, o motor
leria o status gravado no primeiro contato (não segue) pra sempre.

    python3 tests/scripts/teste_segue_gate.py
"""
import os
import shutil
import sys
import tempfile

pasta = tempfile.mkdtemp(prefix="ceq_gate_")
os.environ["DATA_DIR"] = pasta

from app import db, instagram, runtime  # noqa: E402

FALHAS = []
ENVIADAS = []          # (recipient, texto/tipo) na ordem
PERFIL_API = {}        # o que a "Meta" responde no fetch_profile, mutável por caso


def caso(nome, cond, detalhe=""):
    print(("ok   " if cond else "FALHA") + f" {nome}" + (f"  [{detalhe}]" if detalhe and not cond else ""))
    if not cond:
        FALHAS.append(nome)


def post_fake(url, **kw):
    class R:
        status_code = 200
        headers = {"content-type": "application/json"}
        def json(self):
            return {"ok": True}
    corpo = kw.get("json") or {}
    msg = corpo.get("message") or {}
    texto = msg.get("text") or (msg.get("attachment") or {}).get("payload", {}).get("text", "")
    tipo = "attachment" if msg.get("attachment") else "text"
    ENVIADAS.append((str(corpo.get("recipient")), texto or tipo))
    return R()


def fetch_profile_fake(access_token, igsid):
    return dict(PERFIL_API)


GRAFO = {
    "nodes": [
        {"id": "n1", "type": "condition", "data": {"check": "e_seguidor"}},
        {"id": "n_link", "type": "buttons",
         "data": {"text": "Aqui está o link prometido!",
                  "buttons": [{"title": "ABRIR", "type": "url", "url": "https://exemplo.com"}]}},
        {"id": "n_pede", "type": "buttons",
         "data": {"text": "Te mando o link, mas primeiro me segue lá!",
                  "buttons": [{"title": "Já estou seguindo", "key": "ja_sigo"}]}},
        {"id": "n2", "type": "condition", "data": {"check": "e_seguidor"}},
        {"id": "n_denovo", "type": "buttons",
         "data": {"text": "Ainda não te achei lá. Segue e clica de novo!",
                  "buttons": [{"title": "Já estou seguindo", "key": "ja_sigo"}]}},
    ],
    "edges": [
        {"id": "e1", "source": "n1", "target": "n_link", "sourceHandle": "sim"},
        {"id": "e2", "source": "n1", "target": "n_pede", "sourceHandle": "nao"},
        {"id": "e3", "source": "n_pede", "target": "n2", "sourceHandle": "ja_sigo"},
        {"id": "e4", "source": "n2", "target": "n_link", "sourceHandle": "sim"},
        {"id": "e5", "source": "n2", "target": "n_denovo", "sourceHandle": "nao"},
        {"id": "e6", "source": "n_denovo", "target": "n2", "sourceHandle": "ja_sigo"},
    ],
}


def main():
    db.init()
    original_post = instagram.requests.post
    original_fetch = instagram.fetch_profile
    instagram.requests.post = post_fake
    instagram.fetch_profile = fetch_profile_fake
    try:
        acc = db.upsert_account("999", "999", "contateste", "tok", db.in_seconds_iso(86400))
        flow_id = db.create_flow(acc["id"], name="gate seguidor", graph=GRAFO, entry_node="n1")
        flow = db.get_flow(flow_id)

        # caso A: já segue desde o começo -> link direto
        PERFIL_API.update({"username": "ana.segue", "name": "Ana", "profile_pic": "",
                           "follower_count": 10, "is_user_follow_business": True})
        lead_a = db.touch_lead(acc["id"], "111", "kw", "ana.segue")
        db.enrich_lead(acc["id"], "111", PERFIL_API)
        lead_a = db.get_lead(lead_a["id"])
        runtime.start(acc, flow, lead_a, comment_id="c_a")
        caso("A: seguidora recebe o link direto",
             any("link prometido" in t for _, t in ENVIADAS), str(ENVIADAS))
        caso("A: seguidora NÃO recebe pedido pra seguir",
             not any("me segue" in t for _, t in ENVIADAS), str(ENVIADAS))

        # caso B: não segue -> pede; segue no meio, clica -> reconsulta pega o novo status
        ENVIADAS.clear()
        PERFIL_API.update({"username": "beto.naosegue", "name": "Beto",
                           "is_user_follow_business": False})
        lead_b = db.touch_lead(acc["id"], "222", "kw", "beto.naosegue")
        db.enrich_lead(acc["id"], "222", PERFIL_API)
        lead_b = db.get_lead(lead_b["id"])
        motivo = runtime.start(acc, flow, lead_b, comment_id="c_b")
        caso("B: não-seguidor recebe pedido pra seguir e o fluxo espera clique",
             any("me segue" in t for _, t in ENVIADAS) and motivo == "esperando_clique",
             f"{motivo} {ENVIADAS}")

        # caso C: clica sem ter seguido -> reconsulta confirma que não segue -> insiste
        motivo = runtime.resume_postback(acc, lead_b, "ja_sigo")
        caso("C: clicou sem seguir, leva o 'ainda não te achei' e espera de novo",
             any("não te achei" in t for _, t in ENVIADAS) and motivo == "esperando_clique",
             f"{motivo} {ENVIADAS}")
        caso("C: link NÃO saiu pra quem não segue",
             not any("link prometido" in t for _, t in ENVIADAS), str(ENVIADAS))

        # caso B2: agora seguiu de verdade e clica de novo -> link sai
        PERFIL_API["is_user_follow_business"] = True
        motivo = runtime.resume_postback(acc, lead_b, "ja_sigo")
        caso("B2: seguiu no meio do fluxo, reconsulta libera o link",
             any("link prometido" in t for _, t in ENVIADAS), f"{motivo} {ENVIADAS}")
        lead_b = db.get_lead(lead_b["id"])
        caso("B2: status novo ficou gravado no lead", lead_b["is_follower"] == 1,
             str(lead_b["is_follower"]))

        # caso D: API esconde o perfil (fetch retorna {}) -> na dúvida, libera
        ENVIADAS.clear()
        PERFIL_API.clear()
        lead_d = db.touch_lead(acc["id"], "444", "kw", "perfil.oculto")
        lead_d = db.get_lead(lead_d["id"])
        caso("D: lead sem enriquecimento tem is_follower NULL",
             lead_d["is_follower"] is None, str(lead_d["is_follower"]))
        runtime.start(acc, flow, lead_d, comment_id="c_d")
        caso("D: perfil oculto não trava, link sai (fail-open)",
             any("link prometido" in t for _, t in ENVIADAS), str(ENVIADAS))
    finally:
        instagram.requests.post = original_post
        instagram.fetch_profile = original_fetch

    shutil.rmtree(pasta, ignore_errors=True)
    if FALHAS:
        print(f"\n{len(FALHAS)} caso(s) falharam: {FALHAS}")
        sys.exit(1)
    print("\ntodos os casos passaram")


if __name__ == "__main__":
    main()
