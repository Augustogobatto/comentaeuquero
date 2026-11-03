"""Correções da 1.11.2 (review da 1.11.1):

1. Banco que passou pelo bug da 1.11.0 tem duas linhas pra mesma conta (uma no login
   unificado, com token morto, e outra no login do Instagram). A 1.11.1 não juntava.
2. Verificação/envio em voo com o dict velho da conta remarcava "Reconectar" numa
   conta já reconectada (190 do token antigo).
3. Login unificado que devolve token de usuário curto (1-2h) agora vira token longo.

Meta de mentira, nenhuma chamada sai pra rede.
"""
import pytest

from app import db, instagram
from tests.conftest import _Resp
from tests.test_login_unificado import MetaFake


def _limpa():
    c = db.conn()
    c.execute("DELETE FROM accounts")
    c.execute("DELETE FROM events")
    c.execute("DELETE FROM ajustes WHERE chave LIKE 'token_invalido:%'")
    c.commit()


@pytest.fixture(autouse=True)
def _banco_limpo():
    _limpa()
    yield
    _limpa()


def _duas_linhas(fb_token="SYS-VELHO", ig_token="IGAA-1"):
    """Estado deixado pela 1.11.0: unificado primeiro, depois login do IG."""
    c = db.conn()
    fb = c.execute("INSERT INTO accounts (ig_id, ig_user_id, username, access_token, api_modo) "
                   "VALUES ('1784X','1784X','dono',?,'facebook_login')", (fb_token,)).lastrowid
    ig = c.execute("INSERT INTO accounts (ig_id, ig_user_id, username, access_token, api_modo) "
                   "VALUES ('APPSCOPED','1784X','dono',?,'instagram_login')", (ig_token,)).lastrowid
    c.commit()
    return fb, ig


# ---------- 1. duas linhas da mesma conta ----------

def test_reconectar_pelo_ig_junta_a_duplicata():
    fb, ig = _duas_linhas()
    db.upsert_account("APPSCOPED", "1784X", "dono", "IGAA-2", None)
    linhas = db.all_accounts()
    assert len(linhas) == 1
    assert linhas[0]["id"] == ig
    assert db.first_account()["access_token"] == "IGAA-2"
    assert db.first_account()["api_modo"] == "instagram_login"
    assert db.get_account_by_ig_id("1784X")["access_token"] == "IGAA-2"
    assert db.get_account_by_ig_id("APPSCOPED")["id"] == ig


def test_reconectar_pelo_unificado_junta_e_fica_com_o_token_novo():
    fb, ig = _duas_linhas()
    conta = db.upsert_account_fb("1784X", "dono", "SYS-NOVO", None)
    linhas = db.all_accounts()
    assert len(linhas) == 1
    assert conta["access_token"] == "SYS-NOVO" and conta["api_modo"] == "facebook_login"
    assert db.get_account_by_ig_id("1784X")["access_token"] == "SYS-NOVO"
    assert db.first_account()["access_token"] == "SYS-NOVO"


def _popula(conta_id, sufixo, igsid_comum="P1", wa_comum="5511999990000"):
    """Fluxo+gatilho+lead (um em comum com a outra linha)+sessão+tag+campo+template."""
    c = db.conn()
    flow = c.execute("INSERT INTO flows (account_id, name) VALUES (?,?)",
                     (conta_id, f"fluxo-{sufixo}")).lastrowid
    c.execute("INSERT INTO triggers (flow_id, type, keywords) VALUES (?, 'comment', '[\"q\"]')",
              (flow,))
    # regra antiga já convertida (flow_id preenchido), senão o init vira fluxo novo
    c.execute("INSERT INTO rules (account_id, keywords, reply, flow_id) VALUES (?, '[]', 'oi', ?)",
              (conta_id, flow))
    so = c.execute("INSERT INTO leads (account_id, igsid, username, interactions, last_ts, "
                   "first_ts) VALUES (?,?,?,1,?,?)",
                   (conta_id, f"so-{sufixo}", f"u-{sufixo}", "2026-11-01T00:00:00Z",
                    "2026-11-01T00:00:00Z")).lastrowid
    comum = c.execute("INSERT INTO leads (account_id, igsid, username, interactions, last_ts, "
                      "first_ts, last_keyword, wa_id) VALUES (?,?,?,?,?,?,?,?)",
                      (conta_id, igsid_comum, "comum" if sufixo == "fb" else "",
                       2, f"2026-11-0{2 if sufixo == 'fb' else 3}T00:00:00Z",
                       f"2026-10-0{1 if sufixo == 'fb' else 5}T00:00:00Z",
                       f"kw-{sufixo}", wa_comum if sufixo == "fb" else "")).lastrowid
    c.execute("INSERT INTO lead_tags (lead_id, tag) VALUES (?,?)", (comum, f"tag-{sufixo}"))
    c.execute("INSERT INTO lead_tags (lead_id, tag) VALUES (?, 'igual')", (comum,))
    c.execute("INSERT INTO lead_fields (lead_id, key, value) VALUES (?,?,?)",
              (comum, f"campo_{sufixo}", sufixo))
    c.execute("INSERT INTO flow_sessions (account_id, lead_id, flow_id) VALUES (?,?,?)",
              (conta_id, comum, flow))
    pasta = c.execute("INSERT INTO wa_template_pastas (account_id, nome) VALUES (?, 'Vendas')",
                      (conta_id,)).lastrowid
    c.execute("INSERT INTO wa_templates (account_id, nome, idioma, pasta_id) "
              "VALUES (?, 'boas_vindas', 'pt_BR', ?)", (conta_id, pasta))
    c.execute("INSERT INTO wa_templates (account_id, nome, idioma) VALUES (?, ?, 'pt_BR')",
              (conta_id, f"so_{sufixo}"))
    c.execute("INSERT INTO events (account_id, kind) VALUES (?, 'webhook')", (conta_id,))
    c.commit()
    return so, comum


def test_init_junta_duplicata_sem_perder_dado():
    fb, ig = _duas_linhas()
    _popula(fb, "fb")
    _popula(ig, "ig")
    db.set_ajuste(f"token_invalido:{fb}", "2026-11-03T00:00:00Z")
    # a conexão mais recente foi a do login do Instagram
    db.log_event("oauth_ok", fb)
    db.log_event("oauth_ok", ig)

    db.init()
    db.init()   # idempotente

    c = db.conn()
    linhas = db.all_accounts()
    assert [r["id"] for r in linhas] == [ig]
    assert linhas[0]["access_token"] == "IGAA-1"
    assert db.get_account_by_ig_id("1784X")["id"] == ig

    nomes = {r["name"] for r in c.execute("SELECT name FROM flows WHERE account_id=?", (ig,))}
    assert nomes == {"fluxo-fb", "fluxo-ig"}
    assert c.execute("SELECT COUNT(*) FROM triggers t JOIN flows f ON f.id=t.flow_id "
                     "WHERE f.account_id=?", (ig,)).fetchone()[0] == 2
    assert c.execute("SELECT COUNT(*) FROM rules WHERE account_id=?", (ig,)).fetchone()[0] == 2
    assert c.execute("SELECT COUNT(*) FROM events WHERE account_id=? AND kind='webhook'",
                     (ig,)).fetchone()[0] == 2

    leads = {r["igsid"]: dict(r) for r in
             c.execute("SELECT * FROM leads WHERE account_id=?", (ig,))}
    assert set(leads) == {"so-fb", "so-ig", "P1"}
    p1 = leads["P1"]
    assert p1["interactions"] == 4
    assert p1["first_ts"] == "2026-10-01T00:00:00Z"        # o mais antigo
    assert p1["last_ts"] == "2026-11-03T00:00:00Z"         # o mais recente
    assert p1["last_keyword"] == "kw-ig"                   # da interação mais recente
    assert p1["username"] == "comum"                       # vazio herda da outra linha
    assert p1["wa_id"] == "5511999990000"
    tags = {r["tag"] for r in c.execute("SELECT tag FROM lead_tags WHERE lead_id=?", (p1["id"],))}
    assert tags == {"tag-fb", "tag-ig", "igual"}
    campos = {r["key"] for r in c.execute("SELECT key FROM lead_fields WHERE lead_id=?",
                                          (p1["id"],))}
    assert campos == {"campo_fb", "campo_ig"}
    assert c.execute("SELECT COUNT(*) FROM flow_sessions WHERE account_id=? AND lead_id=?",
                     (ig, p1["id"])).fetchone()[0] == 2

    pastas = list(c.execute("SELECT id FROM wa_template_pastas WHERE account_id=?", (ig,)))
    assert len(pastas) == 1
    tpls = {r["nome"]: r["pasta_id"] for r in
            c.execute("SELECT nome, pasta_id FROM wa_templates WHERE account_id=?", (ig,))}
    assert set(tpls) == {"boas_vindas", "so_fb", "so_ig"}
    assert tpls["boas_vindas"] == pastas[0]["id"]

    # nada pendurado na linha apagada
    for t in ("flows", "leads", "rules", "events", "flow_sessions", "wa_templates",
              "wa_template_pastas"):
        assert c.execute(f"SELECT COUNT(*) FROM {t} WHERE account_id=?", (fb,)).fetchone()[0] == 0
    assert db.get_ajuste(f"token_invalido:{fb}") == ""


def test_init_sem_oauth_ok_fica_com_a_linha_mais_nova():
    fb, ig = _duas_linhas()
    db.init()
    assert [r["id"] for r in db.all_accounts()] == [ig]


def test_init_prefere_a_ultima_conexao_mesmo_sendo_a_linha_mais_velha():
    fb, ig = _duas_linhas()
    db.log_event("oauth_ok", ig)
    db.log_event("oauth_ok", fb)   # reconectou pelo unificado por último
    db.init()
    linhas = db.all_accounts()
    assert [r["id"] for r in linhas] == [fb]
    assert linhas[0]["api_modo"] == "facebook_login"


def test_contas_diferentes_nao_se_juntam():
    c = db.conn()
    c.execute("INSERT INTO accounts (ig_id, ig_user_id, access_token, api_modo) "
              "VALUES ('1784A','1784A','t1','facebook_login')")
    c.execute("INSERT INTO accounts (ig_id, ig_user_id, access_token, api_modo) "
              "VALUES ('APPB','1784B','t2','instagram_login')")
    c.commit()
    db.init()
    assert len(db.all_accounts()) == 2


def test_lead_com_mesmo_whatsapp_e_igsid_diferente_junta():
    fb, ig = _duas_linhas()
    c = db.conn()
    c.execute("INSERT INTO leads (account_id, igsid, wa_id) VALUES (?, 'wa:1', '5511888')", (fb,))
    c.execute("INSERT INTO leads (account_id, igsid, wa_id) VALUES (?, 'outro', '5511888')", (ig,))
    c.commit()
    db.init()
    assert c.execute("SELECT COUNT(*) FROM leads WHERE wa_id='5511888'").fetchone()[0] == 1


# ---------- 2. 190 do token velho depois da reconexão ----------

class _R190:
    status_code = 400
    headers = {"content-type": "application/json"}
    text = '{"error":{"code":190}}'

    def json(self):
        return {"error": {"code": 190, "message": "expired"}}


def test_verificar_token_com_dict_velho_nao_marca_conta_reconectada(monkeypatch):
    velha = db.upsert_account_fb("1784Y", "dono", "SYS-VELHO", None)
    db.upsert_account_fb("1784Y", "dono", "SYS-NOVO", None)   # dono reconecta
    instagram.limpa_token_invalido(velha["id"])
    monkeypatch.setattr(instagram.requests, "get", lambda *a, **k: _R190())
    instagram.verificar_token(velha)   # loop de 6h com o snapshot de antes
    atual = db.get_account(velha["id"])
    assert atual["access_token"] == "SYS-NOVO"
    assert not instagram.token_invalido(atual)


def test_envio_com_token_velho_nao_marca_conta_reconectada(monkeypatch):
    db.set_ajuste("throttle_until", "")
    velha = db.upsert_account_fb("1784Y", "dono", "SYS-VELHO", None)
    db.upsert_account_fb("1784Y", "dono", "SYS-NOVO", None)
    monkeypatch.setattr(instagram.requests, "post", lambda *a, **k: _R190())
    ok, _, _ = instagram.post_with_retry("https://graph.facebook.com/x", "SYS-VELHO", {},
                                         conta=velha)
    assert ok is False
    assert not instagram.token_invalido(db.get_account(velha["id"]))


def test_190_do_token_atual_continua_marcando(monkeypatch):
    db.set_ajuste("throttle_until", "")
    conta = db.upsert_account_fb("1784Y", "dono", "SYS-ATUAL", None)
    monkeypatch.setattr(instagram.requests, "get", lambda *a, **k: _R190())
    assert instagram.verificar_token(conta) is False
    assert instagram.token_invalido(conta)
    instagram.limpa_token_invalido(conta["id"])
    monkeypatch.setattr(instagram.requests, "post", lambda *a, **k: _R190())
    instagram.post_with_retry("https://graph.facebook.com/x", "SYS-ATUAL", {}, conta=conta)
    assert instagram.token_invalido(conta)


# ---------- 3. token curto no login unificado ----------

def _meta_unificado(monkeypatch, primeiro, longo=None):
    m = MetaFake()

    def oauth(params):
        if params.get("grant_type") == "fb_exchange_token":
            return (200, longo) if longo else (400, {"error": {"code": 1}})
        return 200, primeiro

    m.rotas[("GET", "/oauth/access_token")] = oauth
    m.rotas[("GET", "/me/assigned_instagram_accounts")] = (
        200, {"data": [{"id": "1784Z", "username": "dono"}]})
    monkeypatch.setattr(instagram.requests, "get", m.get)
    monkeypatch.setattr(instagram.requests, "post", m.post)
    return m


def _trocas(m):
    return [c for c in m.chamadas
            if c["params"].get("grant_type") == "fb_exchange_token"]


def test_token_curto_vira_longo(monkeypatch):
    m = _meta_unificado(monkeypatch, {"access_token": "CURTO", "expires_in": 5400},
                        {"access_token": "LONGO", "expires_in": 5184000})
    contas = instagram.exchange_code_fb("555", "fb-secret", "https://x/cb", "code")
    assert contas[0]["access_token"] == "LONGO"
    assert contas[0]["token_expires_at"] is not None
    st = instagram.token_status({"api_modo": "facebook_login", "id": 0,
                                 "token_expires_at": contas[0]["token_expires_at"]})
    assert 59 < st["dias"] < 61
    troca = _trocas(m)
    assert len(troca) == 1
    assert troca[0]["params"] == {"grant_type": "fb_exchange_token", "client_id": "555",
                                  "client_secret": "fb-secret", "fb_exchange_token": "CURTO"}
    # as contas foram buscadas já com o token longo
    busca = [c for c in m.chamadas if c["url"].endswith("/me/assigned_instagram_accounts")]
    assert busca[0]["params"]["access_token"] == "LONGO"


@pytest.mark.parametrize("tok", [{"access_token": "SUAT"},
                                 {"access_token": "SUAT", "expires_in": 0},
                                 {"access_token": "SUAT", "expires_in": 5184000}])
def test_token_sem_prazo_ou_longo_nao_troca(monkeypatch, tok):
    m = _meta_unificado(monkeypatch, tok, {"access_token": "NAO-USAR", "expires_in": 1})
    contas = instagram.exchange_code_fb("555", "fb-secret", "https://x/cb", "code")
    assert contas[0]["access_token"] == "SUAT"
    assert _trocas(m) == []


def test_troca_falhou_segue_com_o_curto_sem_vazar_segredo(monkeypatch, caplog):
    _meta_unificado(monkeypatch, {"access_token": "CURTO", "expires_in": 3600}, None)
    contas = instagram.exchange_code_fb("555", "fb-secret", "https://x/cb", "code")
    assert contas[0]["access_token"] == "CURTO"
    assert "fb-secret" not in caplog.text and "CURTO" not in caplog.text


def test_init_sobe_mesmo_se_a_fusao_falhar(monkeypatch):
    from app import db
    def explode(*a, **k):
        raise RuntimeError("banco estranho")
    monkeypatch.setattr(db, "fundir_contas_duplicadas", explode)
    db.init()  # não pode levantar
