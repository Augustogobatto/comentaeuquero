"""Simula um fluxo grande (o esqueleto "ímã padrão") de ponta a ponta,
sem Meta: botão com timeout, delay, captura de nome e whats com validação e
retry, tag, condição e mensagem final. É o teste que responde "fluxo grande
funciona no motor?" antes de ligar qualquer um numa conta real.

    python3 tests/scripts/teste_fluxo_grande.py
"""
import os
import shutil
import sys
import tempfile

pasta = tempfile.mkdtemp(prefix="ceq_fluxo_")
os.environ["DATA_DIR"] = pasta

from app import db, instagram, runtime  # noqa: E402

FALHAS = []
ENVIADAS = []          # (recipient, texto/tipo) na ordem


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


# O grafo replica a família A do inventário: o esqueleto que vale pra 11 fluxos.
GRAFO = {
    "nodes": [
        {"id": "n1", "type": "text",
         "data": {"text": "Oi {primeiro_nome}! Chegou o material."}},
        {"id": "n2", "type": "buttons",
         "data": {"text": "Quer o bônus?", "timeout_seconds": 300,
                  "buttons": [{"title": "Quero", "key": "quero"}]}},
        {"id": "n3", "type": "delay", "data": {"minutes": 5}},
        {"id": "n4", "type": "text", "data": {"text": "Pitch: conhece o programa?"}},
        {"id": "n5", "type": "wait_input",
         "data": {"expects": "texto", "save_as": "nome",
                  "text": ""}},
        {"id": "n6", "type": "wait_input",
         "data": {"expects": "telefone", "save_as": "whats",
                  "retry_text": "Manda só os números com DDD, por favor."}},
        {"id": "n7", "type": "action", "data": {"actions": [{"action": "add_tag", "tag": "lead_quente"}]}},
        {"id": "n8", "type": "condition", "data": {"check": "tem_tag", "value": "lead_quente"}},
        {"id": "n9", "type": "text", "data": {"text": "Fechou, {nome}! Te chamo no {whats}."}},
        {"id": "n10", "type": "text", "data": {"text": "Sem tag? Caminho impossivel."}},
    ],
    "edges": [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3", "sourceHandle": "quero"},
        {"id": "e2b", "source": "n2", "target": "n3", "sourceHandle": "timeout"},
        {"id": "e3", "source": "n3", "target": "n4"},
        {"id": "e4", "source": "n4", "target": "n5"},
        {"id": "e5", "source": "n5", "target": "n6"},
        {"id": "e6", "source": "n6", "target": "n7"},
        {"id": "e7", "source": "n7", "target": "n8"},
        {"id": "e8", "source": "n8", "target": "n9", "sourceHandle": "sim"},
        {"id": "e9", "source": "n8", "target": "n10", "sourceHandle": "nao"},
    ],
}


def vence_jobs():
    """Empurra o relógio: todo job pendente e todo timeout vencem agora."""
    c = db.conn()
    c.execute("UPDATE jobs SET run_at=? WHERE status='pendente'", (db.in_seconds_iso(-1),))
    c.execute("UPDATE flow_sessions SET waiting_until=? WHERE waiting_until != ''",
              (db.in_seconds_iso(-1),))
    c.commit()


def main():
    db.init()
    original = instagram.requests.post
    instagram.requests.post = post_fake
    try:
        acc = db.upsert_account("999", "999", "linetest", "tok", db.in_seconds_iso(86400))
        lead = db.touch_lead(acc["id"], "111", "arquetipo", "maria.psi")
        db.enrich_lead(acc["id"], "111", {"username": "maria.psi",
                                          "name": "Maria Clara | Psicóloga",
                                          "profile_pic": "", "follower_count": 800,
                                          "is_user_follow_business": True})
        lead = db.get_lead(lead["id"])
        flow_id = db.create_flow(acc["id"], name="arquetipo", graph=GRAFO, entry_node="n1")
        flow = db.get_flow(flow_id)

        # 1. comentário dispara: private reply do n1 + botões, e para esperando clique
        motivo = runtime.start(acc, flow, lead, comment_id="c_1")
        caso("fluxo para esperando clique no botão", motivo == "esperando_clique", motivo)
        caso("primeira mensagem foi private reply no comentário",
             ENVIADAS and "comment_id" in ENVIADAS[0][0], str(ENVIADAS[:1]))
        caso("{primeiro_nome} rendeu 'Maria' antes de perguntar o nome",
             any("Oi Maria!" in t for _, t in ENVIADAS), str(ENVIADAS))

        # 2. ninguém clicou: timeout do botão cai no ramo certo e agenda o delay
        vence_jobs()
        runtime.tick(account_por_id=lambda _id: acc)
        sess = db.active_session_for_lead(lead["id"])
        caso("timeout do botão seguiu pro delay (job agendado)",
             sess and db.conn().execute(
                 "SELECT COUNT(*) FROM jobs WHERE status='pendente'").fetchone()[0] == 1)

        # 3. delay vence: pitch sai e o fluxo para esperando o nome
        vence_jobs()
        runtime.tick(account_por_id=lambda _id: acc)
        sess = db.active_session_for_lead(lead["id"])
        caso("depois do delay, esperando texto (nome)",
             sess and sess["waiting_for"] == "text", str(sess and sess["waiting_for"]))
        caso("pitch saiu como DM (não private reply)",
             any("Pitch" in t and "comment_id" not in r for r, t in ENVIADAS))

        # 4. pessoa responde o nome
        motivo = runtime.resume_text(acc, lead, "Ana Paula")
        caso("nome salvo no lead", db.get_field(lead["id"], "nome") == "Ana Paula")

        # 5. whats inválido: retry_text sai e o fluxo NÃO anda
        antes = len(ENVIADAS)
        motivo = runtime.resume_text(acc, lead, "meu zap é quarenta e oito")
        caso("telefone inválido segura o fluxo", motivo == "entrada_invalida", motivo)
        caso("retry_text foi enviado", len(ENVIADAS) == antes + 1)

        # 6. whats válido: tag, condição e mensagem final com os dois campos
        motivo = runtime.resume_text(acc, lead, "(48) 99999-0000")
        caso("whats normalizado só com dígitos",
             db.get_field(lead["id"], "whats") == "48999990000",
             db.get_field(lead["id"], "whats"))
        caso("tag aplicada", db.has_tag(lead["id"], "lead_quente"))
        caso("condição foi pro ramo certo e renderizou os campos",
             any("Fechou, Ana Paula! Te chamo no 48999990000." in t for _, t in ENVIADAS),
             str(ENVIADAS[-2:]))
        caso("ramo impossível não disparou",
             not any("impossivel" in t for _, t in ENVIADAS))
        sess = db.get_session(sess["id"])
        caso("sessão concluída", sess["status"] == "concluida", sess["status"])

        # 7. a janela de 24h protege: delay que vence FORA da janela não envia
        lead2 = db.touch_lead(acc["id"], "222", "arquetipo", "outra.pessoa")
        runtime.start(acc, flow, lead2, comment_id="c_2")
        db.conn().execute("UPDATE flow_sessions SET window_expires_at=? WHERE lead_id=?",
                          (db.in_seconds_iso(-10), lead2["id"]))
        # desde a 1.8.0 a janela também mora no lead, por canal: vencer as duas
        db.conn().execute("UPDATE leads SET ig_janela_ate=? WHERE id=?",
                          (db.in_seconds_iso(-10), lead2["id"]))
        db.conn().commit()
        antes = len(ENVIADAS)
        vence_jobs()
        runtime.tick(account_por_id=lambda _id: acc)
        vence_jobs()
        runtime.tick(account_por_id=lambda _id: acc)
        caso("fora da janela de 24h, nada é enviado", len(ENVIADAS) == antes,
             str(ENVIADAS[antes:]))
        fora = db.conn().execute(
            "SELECT COUNT(*) FROM events WHERE kind='fora_da_janela'").fetchone()[0]
        caso("expiração logada como fora_da_janela", fora >= 1)
    finally:
        instagram.requests.post = original

    shutil.rmtree(pasta, ignore_errors=True)
    if FALHAS:
        print(f"\n{len(FALHAS)} caso(s) falharam: {FALHAS}")
        sys.exit(1)
    print("\ntodos os casos passaram")


if __name__ == "__main__":
    main()
