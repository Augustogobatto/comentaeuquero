"""Teste da trava de rate limit: balde, detecção de 80002, cooldown e fila.

Roda sozinho, sem Meta e sem serviço no ar:
    DATA_DIR=/tmp/ceq_teste_rate python3 tests/scripts/teste_rate.py
"""
import os
import shutil
import sys
import tempfile

pasta = tempfile.mkdtemp(prefix="ceq_rate_")
os.environ["DATA_DIR"] = pasta

from app import alerta, db, instagram, runtime  # noqa: E402  (DATA_DIR antes)

FALHAS = []


def caso(nome, cond):
    print(("ok   " if cond else "FALHA") + f" {nome}")
    if not cond:
        FALHAS.append(nome)


class RespostaFake:
    def __init__(self, status, body, headers=None):
        self.status_code = status
        self._body = body
        self.headers = {"content-type": "application/json", **(headers or {})}

    def json(self):
        return self._body


def main():
    db.init()
    conta = {"ig_id": "999", "access_token": "tok"}

    # 1. balde de fichas
    balde = runtime.RateLimiter(por_hora=2)
    caso("balde dá 2 fichas", balde.tenta() and balde.tenta())
    caso("balde nega a 3ª", not balde.tenta())
    caso("balde diz quanto esperar", balde.espera_ate() > 0)

    # 2. throttle da Meta (80002 num HTTP 400, que o retry antigo ignorava)
    chamadas = []

    def post_throttle(url, **kw):
        chamadas.append(url)
        return RespostaFake(400, {"error": {"code": 80002, "message": "limit"}},
                            {"X-Business-Use-Case-Usage":
                             '{"123":[{"estimated_time_to_regain_access": 2}]}'})

    original = instagram.requests.post
    instagram.requests.post = post_throttle
    try:
        ok, status, body = instagram.send_text(conta, {"id": "111"}, "oi")
        caso("throttle devolve ok=None (reagendar), não falha", ok is None)
        caso("cooldown gravado ~2 min (header em minutos)",
             100 < instagram.cooldown_restante() <= 121)
        caso("não insistiu no retry contra throttle", len(chamadas) == 1)

        ok2, _, corpo2 = instagram.send_text(conta, {"id": "111"}, "oi de novo")
        caso("em cooldown, nem bate na API", ok2 is None and len(chamadas) == 1)
        caso("motivo diz que é cooldown", "cooldown" in str(corpo2))
    finally:
        instagram.requests.post = original

    # 3. cooldown vencido libera
    db.set_ajuste("throttle_until", db.in_seconds_iso(-10))
    caso("cooldown no passado = livre", instagram.cooldown_restante() == 0.0)

    # 4. job guarda o comment_id (private reply adiada não pode virar DM comum)
    acc = db.upsert_account("999", "999", "teste", "tok", db.in_seconds_iso(86400))
    lead = db.touch_lead(acc["id"], "111", "quero", "fulano")
    flow_id = db.create_flow(acc["id"], name="quero", graph={
        "nodes": [{"id": "n1", "type": "text", "data": {"text": "oi"}}], "edges": []},
        entry_node="n1")
    sess = db.open_session(acc["id"], lead["id"], flow_id, node_id="n1",
                           window_expires_at=db.in_seconds_iso(3600))
    db.schedule_job(sess, "n1", db.in_seconds_iso(-1), comment_id="c_777")
    vencidos = db.due_jobs()
    caso("job vencido volta com comment_id", vencidos
         and vencidos[0].get("comment_id") == "c_777")

    # 5. contador de envios da última hora
    db.log_event("fluxo_envio", acc["id"], ok=1)
    db.log_event("private_reply", acc["id"], ok=0)   # tentativa falha também conta
    db.log_event("webhook", acc["id"])               # recebimento não conta
    caso("envios_na_ultima_hora conta só saída", db.envios_na_ultima_hora(acc["id"]) == 2)

    # 6. teto editável ao vivo, com trilhos
    antes = runtime.teto_atual()
    caso("teto clampa no máximo oficial (750)", runtime.aplicar_teto(9999) == 750)
    caso("teto clampa no mínimo (10)", runtime.aplicar_teto(1) == 10)
    caso("teto vale na hora, sem restart", runtime.teto_atual() == 10)
    runtime.aplicar_teto(antes)

    # 7. alerta: painel manda, .env é só semente
    os.environ["ALERTA_TELEGRAM_TOKEN"] = "tok_env"
    os.environ["ALERTA_TELEGRAM_CHAT"] = "123"
    db.set_ajuste("alerta_telegram_token", "off")
    caso("desativado no painel ignora o .env", alerta.credenciais() == ("", ""))
    db.set_ajuste("alerta_telegram_token", "")
    caso("sem ajuste salvo, cai no .env", alerta.credenciais() == ("tok_env", "123"))
    db.set_ajuste("alerta_telegram_token", "tok_painel")
    db.set_ajuste("alerta_telegram_chat", "456")
    caso("ajuste do painel vence o .env", alerta.credenciais() == ("tok_painel", "456"))

    shutil.rmtree(pasta, ignore_errors=True)
    if FALHAS:
        print(f"\n{len(FALHAS)} caso(s) falharam: {FALHAS}")
        sys.exit(1)
    print("\ntodos os casos passaram")


if __name__ == "__main__":
    main()
