"""Teste das travas de segurança: freio do login, OAuth fechado, teto de IA e CSV.

Roda sozinho, sem Meta e sem serviço no ar:
    python3 tests/scripts/teste_seguranca.py
"""
import os
import shutil
import sys
import tempfile

pasta = tempfile.mkdtemp(prefix="ceq_seg_")
os.environ["DATA_DIR"] = pasta
os.environ["ADMIN_PASSWORD"] = "senha-com-ç-e-ã"
os.environ["META_APP_ID"] = "123"
os.environ["META_APP_SECRET"] = "SEGREDO-DO-APP-XYZ"
os.environ["BASE_URL"] = "https://ceq.exemplo.com"
os.environ["WEBHOOK_VERIFY_TOKEN"] = "verificação"
os.environ["AI_API_KEY"] = "chave-de-teste"
os.environ["CEQ_IA_POR_LEAD_HORA"] = "3"

import requests  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db, instagram, main, runtime  # noqa: E402  (env antes)

FALHAS = []
HTTPS = {"x-forwarded-proto": "https"}


def caso(nome, cond, detalhe=""):
    print(("ok   " if cond else "FALHA") + f" {nome}" + (f"  [{detalhe}]" if detalhe and not cond else ""))
    if not cond:
        FALHAS.append(nome)


def zera_login():
    main.LOGIN_TENTATIVAS.clear()
    main.LOGIN_FALHAS_GLOBAIS.clear()


def login(cli, senha, xff=None):
    cab = dict(HTTPS)
    if xff:
        cab["x-forwarded-for"] = xff
    return cli.post("/login", data={"senha": senha}, headers=cab, follow_redirects=False)


def testa_login():
    print("\n[1] freio do login")
    # atrás do proxy (conexão vem de 127.0.0.1): o proxy anexa o IP real no fim
    proxy = TestClient(main.app, client=("127.0.0.1", 5000))

    zera_login()
    codigos = [login(proxy, "errada", f"10.9.{i}.1, 203.0.113.7").status_code for i in range(8)]
    caso("trocar o começo do X-Forwarded-For não escapa do bloqueio", 429 in codigos, str(codigos))
    caso("as 5 primeiras tentativas ainda são 401", codigos[:5] == [401] * 5, str(codigos))

    zera_login()
    for i in range(6):
        login(proxy, "errada", "198.51.100.9, 203.0.113.7")
    r = login(proxy, "senha-com-ç-e-ã", "203.0.113.7, 198.51.100.9")
    caso("forjar o IP do dono no começo da lista não tranca o dono", r.status_code == 303,
         str(r.status_code))

    # exposto direto (socket é IP público): o cabeçalho inteiro é do cliente
    zera_login()
    # (8.8.8.8 e não um IP de documentação: o ipaddress trata 203.0.113.x como privado)
    direto = TestClient(main.app, client=("8.8.8.8", 5000))
    codigos = [login(direto, "errada", f"10.9.{i}.1").status_code for i in range(8)]
    caso("sem proxy, o X-Forwarded-For é ignorado", 429 in codigos, str(codigos))

    # teto geral: cada tentativa de um IP verdadeiro diferente
    zera_login()
    codigos = [login(proxy, "errada", f"203.0.{i // 250}.{i % 250 + 1}").status_code
               for i in range(main.LOGIN_GLOBAL_LIMITE + 5)]
    caso("teto geral segura quem troca de IP de verdade",
         codigos.count(401) == main.LOGIN_GLOBAL_LIMITE and codigos[-1] == 429,
         f"401={codigos.count(401)} 429={codigos.count(429)}")
    caso("dicionário de IPs não cresce sem limite", len(main.LOGIN_TENTATIVAS) <= main.LOGIN_IPS_MAX)

    zera_login()
    r = login(proxy, "senha-com-ç-e-ã", "203.0.113.7")
    caso("senha com acento entra", r.status_code == 303 and "ceq_session" in r.cookies,
         str(r.status_code))
    r2 = login(proxy, "outra-com-ç", "203.0.113.7")
    caso("senha errada com acento dá 401, não erro 500", r2.status_code == 401, str(r2.status_code))
    r3 = proxy.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verificação",
                                       "hub.challenge": "42"})
    caso("verify token com acento funciona", r3.status_code == 200 and r3.text == "42",
         str(r3.status_code))
    r4 = proxy.post("/webhook", content=b"{}", headers={"X-Hub-Signature-256": "sha256=ç".encode("latin-1")})
    caso("assinatura de webhook com lixo dá 403, não 500", r4.status_code == 403, str(r4.status_code))
    zera_login()
    return r.cookies["ceq_session"]


def testa_oauth(sessao):
    print("\n[2] conexão do Instagram só pra quem está logado")
    anon = TestClient(main.app, client=("127.0.0.1", 5000))
    r = anon.get("/auth/start", follow_redirects=False)
    caso("/auth/start sem login manda pro /login",
         r.status_code == 303 and r.headers["location"] == "/login", r.headers.get("location", ""))
    antes = len(db.all_accounts())
    eventos = db.conn().execute("SELECT COUNT(*) FROM events").fetchone()[0]
    r = anon.get("/auth/callback", params={"code": "abc", "error": "x" * 4000},
                 follow_redirects=False)
    caso("/auth/callback sem login não processa nada",
         r.status_code == 303 and len(db.all_accounts()) == antes
         and db.conn().execute("SELECT COUNT(*) FROM events").fetchone()[0] == eventos)

    dono = TestClient(main.app, client=("127.0.0.1", 5000), base_url="https://ceq.exemplo.com")
    dono.cookies.set("ceq_session", sessao)
    r = dono.get("/auth/start", follow_redirects=False)
    destino = r.headers.get("location", "")
    state = r.cookies.get(main.OAUTH_STATE_COOKIE, "")
    caso("logado, /auth/start leva pra Meta com state",
         destino.startswith(instagram.OAUTH_AUTHORIZE) and state and f"state={state}" in destino,
         destino[:120])

    r = dono.get("/auth/callback", params={"code": "abc", "state": "errado"}, follow_redirects=False)
    caso("state errado é recusado", r.status_code == 400, str(r.status_code))

    # a Meta falha na segunda troca: a exceção do requests carrega a URL com o segredo
    def post_ok(url, **kw):
        class R:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return {"access_token": "TOKEN-CURTO-ABC", "user_id": 1}
        return R()

    def get_falha(url, params=None, **kw):
        resp = requests.Response()
        resp.status_code = 400
        resp.url = requests.Request("GET", url, params=params).prepare().url
        resp.raise_for_status()

    orig_post, orig_get = instagram.requests.post, instagram.requests.get
    instagram.requests.post, instagram.requests.get = post_ok, get_falha
    try:
        r = dono.get("/auth/callback", params={"code": "abc", "state": state},
                     follow_redirects=False)
    finally:
        instagram.requests.post, instagram.requests.get = orig_post, orig_get
    log = db.conn().execute(
        "SELECT payload FROM events WHERE kind='oauth_erro' ORDER BY id DESC LIMIT 1").fetchone()[0]
    caso("falha da Meta responde erro genérico", r.status_code == 502, str(r.status_code))
    caso("a resposta não traz o App Secret nem o token",
         "SEGREDO-DO-APP-XYZ" not in r.text and "TOKEN-CURTO-ABC" not in r.text, r.text[:200])
    caso("o log também não", "SEGREDO-DO-APP-XYZ" not in log and "TOKEN-CURTO-ABC" not in log
         and "client_secret=***" in log, log[:200])


def testa_ia():
    print("\n[3] nó de IA não gasta a chave à toa")
    chamadas = []
    enviadas = []

    def post_fake(url, **kw):
        class R:
            status_code = 200
            headers = {"content-type": "application/json"}
            def json(self):
                if "anthropic" in url:
                    return {"content": [{"type": "text", "text": "resposta da IA"}]}
                return {"ok": True}
        if "anthropic" in url:
            chamadas.append(url)
        else:
            enviadas.append(((kw.get("json") or {}).get("message") or {}).get("text", ""))
        return R()

    grafo = {"nodes": [{"id": "n1", "type": "ai",
                        "data": {"prompt": "responda {username}", "fallback": "texto reserva"}}],
             "edges": []}
    orig_rt, orig_ig = runtime.requests.post, instagram.requests.post
    runtime.requests.post = instagram.requests.post = post_fake
    orig_throttle, runtime.THROTTLE_S = runtime.THROTTLE_S, 0
    balde = runtime.LIMITER
    try:
        acc = db.upsert_account("999", "999", "donoteste", "tok", db.in_seconds_iso(86400))
        lead = db.touch_lead(acc["id"], "111", "kw", "curioso")
        flow = db.get_flow(db.create_flow(acc["id"], name="ia", graph=grafo, entry_node="n1"))

        runtime.LIMITER = runtime.RateLimiter(por_hora=1)
        runtime.LIMITER.fichas = 0.0
        motivos = [runtime.start(acc, flow, lead) for _ in range(5)]
        caso("sem ficha de envio, a IA não é chamada", len(chamadas) == 0, f"{len(chamadas)} chamadas")
        caso("e o envio fica agendado", set(motivos) == {"adiado_rate_limit"}, str(motivos))

        runtime.LIMITER = runtime.RateLimiter(por_hora=500)
        for _ in range(6):
            runtime.start(acc, flow, lead)
        caso("teto por pessoa: 6 disparos, só 3 chamadas pagas", len(chamadas) == 3,
             f"{len(chamadas)} chamadas")
        caso("quem passou do teto recebe o texto reserva",
             enviadas.count("resposta da IA") == 3 and enviadas.count("texto reserva") == 3,
             str(enviadas))

        outro = db.touch_lead(acc["id"], "222", "kw", "outra.pessoa")
        runtime.start(acc, flow, outro)
        caso("o teto é por pessoa, outra pessoa segue recebendo IA", len(chamadas) == 4,
             f"{len(chamadas)} chamadas")
    finally:
        runtime.requests.post, instagram.requests.post = orig_rt, orig_ig
        runtime.THROTTLE_S = orig_throttle
        runtime.LIMITER = balde
    return acc


def testa_csv(sessao, acc):
    print("\n[4] CSV de leads não vira fórmula")
    perfis = {"333": "=HYPERLINK(\"http://evil.example\",\"clique\")", "444": "@SUM(1+1)",
              "555": "+cmd|' /C calc'!A0", "666": "Maria Clara"}
    for igsid, nome in perfis.items():
        lead = db.touch_lead(acc["id"], igsid, "kw", f"user{igsid}")
        db.enrich_lead(acc["id"], igsid, {"username": f"user{igsid}", "name": nome,
                                          "profile_pic": "", "follower_count": 1,
                                          "is_user_follow_business": True})
        db.set_field(lead["id"], "whats", "+55 (48) 99999-0000")
        db.set_field(lead["id"], "obs", "-2+3")
    dono = TestClient(main.app, client=("127.0.0.1", 5000), base_url="https://ceq.exemplo.com")
    dono.cookies.set("ceq_session", sessao)
    r = dono.get("/api/export.csv", params={"tipo": "leads"})
    texto = r.text
    linhas = texto.split("\n")
    caso("exportou", r.status_code == 200 and "username" in linhas[0], str(r.status_code))
    perigosas = [c for l in linhas for c in __import__("csv").reader([l]).__next__()
                 if c[:1] in ("=", "@")]
    caso("nenhuma célula começa com = ou @", not perigosas, str(perigosas))
    caso("a fórmula saiu como texto", "'=HYPERLINK" in texto and "'@SUM" in texto
         and "'+cmd" in texto and "'-2+3" in texto)
    caso("telefone com +55 continua cru", "+55 (48) 99999-0000" in texto
         and "'+55" not in texto)
    caso("nome normal não muda", "Maria Clara" in texto and "'Maria" not in texto)


def main_():
    db.init()
    try:
        sessao = testa_login()
        testa_oauth(sessao)
        acc = testa_ia()
        testa_csv(sessao, acc)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    print("\n" + ("todos os casos passaram" if not FALHAS else f"{len(FALHAS)} FALHARAM: {FALHAS}"))
    sys.exit(1 if FALHAS else 0)


if __name__ == "__main__":
    main_()
