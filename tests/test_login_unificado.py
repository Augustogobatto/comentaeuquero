"""Login unificado / login do Facebook (1.11.0), com a Meta de mentira.

Nenhuma chamada sai pra rede: requests.get/post do app.instagram respondem por
rota. O que estes testes NÃO provam (precisa de app real da Meta) está no CHANGELOG.
"""
import hashlib
import hmac
import json
from urllib.parse import parse_qs, urlparse

import pytest

from app import db, instagram, segredos

FB = "https://graph.facebook.com/v23.0"
IG = "https://graph.instagram.com/v23.0"
BASE = "https://ceq.teste"


class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code} para url ...client_secret=SEGREDO-X&code=abc")


class MetaFake:
    """Responde pelo fim da URL (sem a query). `rotas[(metodo, sufixo)] = (status, body)`
    ou uma função (params) -> (status, body)."""

    def __init__(self):
        self.rotas = {}
        self.chamadas = []

    def _resp(self, metodo, url, params, corpo, headers):
        self.chamadas.append({"metodo": metodo, "url": url, "params": params or {},
                              "corpo": corpo, "headers": headers or {}})
        for (m, sufixo), r in self.rotas.items():
            if m == metodo and url.endswith(sufixo):
                if callable(r):
                    r = r(params or corpo or {})
                return _Resp(*r)
        return _Resp(404, {"error": {"message": "rota nao mapeada", "code": 100}})

    def get(self, url, params=None, headers=None, timeout=None, **kw):
        return self._resp("GET", url, params, None, headers)

    def post(self, url, json=None, data=None, params=None, headers=None, timeout=None, **kw):
        return self._resp("POST", url, params, json if json is not None else data, headers)

    def urls(self, metodo=None):
        return [c["url"] for c in self.chamadas if metodo in (None, c["metodo"])]


@pytest.fixture
def meta(monkeypatch):
    m = MetaFake()
    monkeypatch.setattr(instagram.requests, "get", m.get)
    monkeypatch.setattr(instagram.requests, "post", m.post)
    db.set_ajuste("throttle_until", "")
    return m


@pytest.fixture
def modo_fb(monkeypatch):
    """Instância configurada no login unificado, sem conta conectada."""
    from app import main
    for v in ("CEQ_ENCRYPTION_KEY", "META_APP_ID", "META_APP_SECRET", "META_LOGIN_MODO",
              "META_FB_APP_ID", "META_FB_APP_SECRET", "META_FB_CONFIG_ID"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(main, "BASE_URL", BASE)
    db.conn().execute("DELETE FROM accounts")
    db.conn().commit()
    segredos.guardar("meta_fb_app_id", "555")
    segredos.guardar("meta_fb_app_secret", "fb-secret")
    segredos.guardar("meta_fb_config_id", "999")
    db.set_ajuste("meta_login_modo", "facebook_login")
    yield main
    for k in ("meta_fb_app_id", "meta_fb_app_secret", "meta_fb_config_id", "oauth_pendente"):
        segredos.guardar(k, "")
    db.set_ajuste("meta_login_modo", "")
    db.conn().execute("DELETE FROM ajustes WHERE chave LIKE 'token_invalido:%'")
    db.conn().commit()


@pytest.fixture
def painel(client, modo_fb, monkeypatch):
    from tests.conftest import _login
    return _login(client, monkeypatch)


def _rotas_unificado(meta, contas, token="SUAT-1", expires_in=None):
    tok = {"access_token": token, "token_type": "bearer"}
    if expires_in:
        tok["expires_in"] = expires_in
    meta.rotas[("GET", "/oauth/access_token")] = (200, tok)
    meta.rotas[("GET", "/me/assigned_instagram_accounts")] = (200, {"data": contas})
    meta.rotas[("POST", "/subscribed_apps")] = (200, {"success": True})


def _comeca(cliente):
    r = cliente.get("/auth/start", follow_redirects=False)
    assert r.status_code in (302, 307)
    q = parse_qs(urlparse(r.headers["location"]).query)
    return r.headers["location"], q


# ---------- URL de autorização ----------

def test_authorize_url_com_config_id_sem_scope():
    url = instagram.authorize_url_fb("555", f"{BASE}/auth/callback", "st", "999")
    assert url.startswith("https://www.facebook.com/v23.0/dialog/oauth?")
    q = parse_qs(urlparse(url).query)
    assert q["config_id"] == ["999"] and q["response_type"] == ["code"]
    assert q["redirect_uri"] == [f"{BASE}/auth/callback"] and q["state"] == ["st"]
    assert "scope" not in q


def test_authorize_url_sem_config_id_usa_scopes():
    q = parse_qs(urlparse(instagram.authorize_url_fb("555", f"{BASE}/cb", "st")).query)
    assert "config_id" not in q
    assert "instagram_manage_messages" in q["scope"][0]
    assert "pages_show_list" in q["scope"][0]


def test_auth_start_no_modo_fb_vai_pro_facebook(painel):
    url, q = _comeca(painel)
    assert url.startswith("https://www.facebook.com/")
    assert q["client_id"] == ["555"] and q["config_id"] == ["999"]


def test_auth_start_modo_ig_continua_igual(painel):
    db.set_ajuste("meta_login_modo", "instagram_login")
    segredos.guardar("meta_app_id", "111")
    try:
        url, q = _comeca(painel)
        assert url.startswith("https://www.instagram.com/oauth/authorize?client_id=111")
    finally:
        segredos.guardar("meta_app_id", "")


# ---------- callback ----------

def test_callback_feliz_login_unificado(painel, meta):
    _rotas_unificado(meta, [{"id": "17841400000000001", "username": "loja"}])
    meta.rotas[("GET", "/17841400000000001")] = (200, {"profile_picture_url": ""})
    _, q = _comeca(painel)
    r = painel.get(f"/auth/callback?code=abc&state={q['state'][0]}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/painel?conectado=1"

    conta = db.first_account()
    assert conta["api_modo"] == "facebook_login" and conta["page_id"] == ""
    assert conta["ig_id"] == conta["ig_user_id"] == "17841400000000001"
    assert conta["access_token"] == "SUAT-1" and conta["token_expires_at"] is None
    assert conta["username"] == "loja"

    troca = meta.chamadas[0]
    assert troca["url"] == f"{FB}/oauth/access_token"
    assert troca["params"]["client_id"] == "555" and troca["params"]["client_secret"] == "fb-secret"
    assert troca["params"]["redirect_uri"] == f"{BASE}/auth/callback"
    # não tenta virar token longo: token do sistema não passa por fb_exchange_token
    assert not any((c["params"] or {}).get("grant_type") == "fb_exchange_token"
                   for c in meta.chamadas)
    sub = [c for c in meta.chamadas if c["url"].endswith("/subscribed_apps")][0]
    assert sub["url"] == f"{FB}/17841400000000001/subscribed_apps"
    assert sub["corpo"]["subscribed_fields"] == "comments,live_comments,messages,messaging_postbacks"
    assert sub["corpo"]["access_token"] == "SUAT-1"

    # painel: sem prazo, sem "renova automaticamente"
    html = painel.get("/painel").text
    assert "login unificado" in html and "sem prazo de validade" in html
    assert "renova automaticamente" not in html


def test_callback_com_expiracao_guarda_prazo(painel, meta):
    _rotas_unificado(meta, [{"id": "17841400000000002", "username": "x"}], expires_in=5184000)
    _, q = _comeca(painel)
    painel.get(f"/auth/callback?code=abc&state={q['state'][0]}", follow_redirects=False)
    st = instagram.token_status(db.first_account())
    assert st["renova"] is False and 59 < st["dias"] < 61


def test_callback_sem_state_recusa(painel, meta):
    _rotas_unificado(meta, [{"id": "1", "username": "x"}])
    _comeca(painel)
    r = painel.get("/auth/callback?code=abc&state=outro", follow_redirects=False)
    assert r.status_code == 400 and meta.chamadas == []


def test_callback_exige_login(client, modo_fb, meta):
    r = client.get("/auth/callback?code=abc&state=x", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_varias_contas_dono_escolhe(painel, meta):
    _rotas_unificado(meta, [{"id": "17841400000000010", "username": "primeira"},
                            {"id": "17841400000000020", "username": "segunda"}])
    _, q = _comeca(painel)
    st = q["state"][0]
    r = painel.get(f"/auth/callback?code=abc&state={st}", follow_redirects=False)
    assert r.status_code == 200
    assert "@primeira" in r.text and "@segunda" in r.text
    assert "SUAT-1" not in r.text                    # token não vai pro navegador
    assert db.first_account() is None                # nada conectado antes da escolha

    # state errado não conecta
    r = painel.post("/auth/escolher", data={"state": "x", "ig": "17841400000000020"},
                    follow_redirects=False)
    assert r.status_code == 400 and db.first_account() is None

    r = painel.post("/auth/escolher", data={"state": st, "ig": "17841400000000020"},
                    follow_redirects=False)
    assert r.status_code == 303
    conta = db.first_account()
    assert conta["ig_user_id"] == "17841400000000020" and conta["username"] == "segunda"
    # escolha é de uso único
    r = painel.post("/auth/escolher", data={"state": st, "ig": "17841400000000010"},
                    follow_redirects=False)
    assert r.status_code == 400


def test_escolha_vencida_recusa(painel, meta):
    _rotas_unificado(meta, [{"id": "a1", "username": "a"}, {"id": "b2", "username": "b"}])
    _, q = _comeca(painel)
    st = q["state"][0]
    painel.get(f"/auth/callback?code=abc&state={st}", follow_redirects=False)
    p = json.loads(segredos.ler("oauth_pendente"))
    p["ate"] = 1
    segredos.guardar("oauth_pendente", json.dumps(p))
    r = painel.post("/auth/escolher", data={"state": st, "ig": "a1"}, follow_redirects=False)
    assert r.status_code == 400 and db.first_account() is None


def test_sem_instagram_vinculado(painel, meta):
    meta.rotas[("GET", "/oauth/access_token")] = (200, {"access_token": "USER-1"})
    meta.rotas[("GET", "/me/assigned_instagram_accounts")] = (200, {"data": []})
    meta.rotas[("GET", "/me/accounts")] = (200, {"data": [
        {"id": "PG1", "name": "Página sem IG", "access_token": "PAGE-1"}]})
    _, q = _comeca(painel)
    r = painel.get(f"/auth/callback?code=abc&state={q['state'][0]}", follow_redirects=False)
    assert r.status_code == 400
    assert "nenhuma conta profissional do Instagram" in r.text
    assert db.first_account() is None
    ev = db.conn().execute("select payload from events where kind='oauth_erro' "
                           "order by id desc limit 1").fetchone()[0]
    assert "sem_conta_instagram" in ev


def test_caminho_classico_com_pagina(painel, meta):
    """App antigo com login do Facebook (sem config_id): token de usuário -> longo ->
    página com instagram_business_account. Envio sai por /{page-id}/messages."""
    segredos.guardar("meta_fb_config_id", "")
    meta.rotas[("GET", "/oauth/access_token")] = lambda p: (
        (200, {"access_token": "USER-LONGO", "expires_in": 5183000})
        if p.get("grant_type") == "fb_exchange_token" else (200, {"access_token": "USER-CURTO"}))
    meta.rotas[("GET", "/me/assigned_instagram_accounts")] = (
        400, {"error": {"message": "Tried accessing nonexisting field", "code": 100}})
    meta.rotas[("GET", "/me/accounts")] = lambda p: (
        (200, {"data": [{"id": "PG1", "name": "Loja", "access_token": "PAGE-TOK",
                         "instagram_business_account": {"id": "17841400000000030"}}]})
        if p.get("access_token") == "USER-LONGO" else (400, {"error": {"code": 190}}))
    meta.rotas[("GET", "/17841400000000030")] = (200, {"username": "lojinha"})
    meta.rotas[("POST", "/subscribed_apps")] = (200, {"success": True})
    _, q = _comeca(painel)
    assert "scope" in q and "config_id" not in q
    r = painel.get(f"/auth/callback?code=abc&state={q['state'][0]}", follow_redirects=False)
    assert r.status_code == 303
    conta = db.first_account()
    assert conta["page_id"] == "PG1" and conta["access_token"] == "PAGE-TOK"
    assert conta["username"] == "lojinha" and conta["token_expires_at"] is None
    sub = [c for c in meta.chamadas if c["url"].endswith("/subscribed_apps")][0]
    assert sub["url"] == f"{FB}/PG1/subscribed_apps" and sub["corpo"]["access_token"] == "PAGE-TOK"

    meta.chamadas.clear()
    meta.rotas[("POST", "/messages")] = (200, {"message_id": "m1"})
    ok, _, _ = instagram.send_text(conta, {"comment_id": "C1"}, "oi")
    assert ok and meta.chamadas[0]["url"] == f"{FB}/PG1/messages"
    assert meta.chamadas[0]["headers"]["Authorization"] == "Bearer PAGE-TOK"


def test_conta_antiga_vira_fb_na_mesma_linha(painel, meta):
    """Quem conectou pelo login do Instagram e reconecta pelo unificado continua na
    mesma conta (fluxos e leads ficam)."""
    antiga = db.upsert_account("APP-SCOPED-9", "17841400000000040", "velha", "IGAA-tok",
                               "2099-01-01T00:00:00Z")
    _rotas_unificado(meta, [{"id": "17841400000000040", "username": "velha"}])
    _, q = _comeca(painel)
    painel.get(f"/auth/callback?code=abc&state={q['state'][0]}", follow_redirects=False)
    contas = db.all_accounts()
    assert len(contas) == 1 and contas[0]["id"] == antiga["id"]
    assert contas[0]["api_modo"] == "facebook_login" and contas[0]["access_token"] == "SUAT-1"
    assert instagram.no_ig(contas[0]) == "17841400000000040"


def test_erro_da_meta_nao_vaza_segredo(painel, meta):
    meta.rotas[("GET", "/oauth/access_token")] = (400, {"error": {"message": "bad code"}})
    _, q = _comeca(painel)
    r = painel.get(f"/auth/callback?code=abc&state={q['state'][0]}", follow_redirects=False)
    assert r.status_code == 502 and "SEGREDO-X" not in r.text
    ev = db.conn().execute("select payload from events where kind='oauth_erro' "
                           "order by id desc limit 1").fetchone()[0]
    assert "SEGREDO-X" not in ev and "client_secret=***" in ev


# ---------- envio ----------

def _conta_fb(page_id=""):
    db.conn().execute("DELETE FROM accounts")
    db.conn().commit()
    return db.upsert_account_fb("17841400000000050", "loja", "SUAT-9", None, page_id)


def test_envio_unificado_usa_graph_facebook(modo_fb, meta):
    conta = _conta_fb()
    meta.rotas[("POST", "/messages")] = (200, {"message_id": "m"})
    meta.rotas[("POST", "/replies")] = (200, {"id": "r"})
    instagram.send_private_reply(conta, "C9", "oi")
    instagram.send_text(conta, {"id": "IGSID1"}, "texto")
    instagram.send_buttons(conta, {"id": "IGSID1"}, "escolha",
                           [{"title": "Quero", "key": "k1"}, {"title": "Site", "url": "https://x.y"}])
    instagram.send_quick_replies(conta, {"id": "IGSID1"}, "e aí?", [{"title": "Sim", "key": "s"}])
    instagram.send_media(conta, {"id": "IGSID1"}, "https://x.y/a.jpg")
    instagram.send_carousel(conta, {"id": "IGSID1"}, [{"title": "A", "url": "https://x.y"}])
    instagram.send_public_reply(conta, "C9", "valeu")
    urls = meta.urls("POST")
    assert urls[:6] == [f"{FB}/17841400000000050/messages"] * 6
    assert urls[6] == f"{FB}/C9/replies"
    assert all(c["headers"]["Authorization"] == "Bearer SUAT-9" for c in meta.chamadas)
    assert meta.chamadas[0]["corpo"]["recipient"] == {"comment_id": "C9"}
    assert not any("graph.instagram.com" in u for u in meta.urls())


def test_leituras_unificado(modo_fb, meta):
    conta = _conta_fb()
    meta.rotas[("GET", "/IGSID7")] = (200, {"name": "Ana", "username": "ana",
                                            "is_user_follow_business": True})
    meta.rotas[("GET", "/17841400000000050")] = (200, {"profile_picture_url": "https://cdn/x.jpg"})
    meta.rotas[("GET", "/17841400000000050/media")] = (200, {"data": [{"id": "M1"}]})
    assert instagram.fetch_profile(conta, "IGSID7")["username"] == "ana"
    assert instagram.fetch_own_pic(conta) == "https://cdn/x.jpg"
    assert instagram.fetch_media_list(conta) == [{"id": "M1"}]
    assert meta.urls("GET") == [f"{FB}/IGSID7", f"{FB}/17841400000000050",
                                f"{FB}/17841400000000050/media"]
    assert "is_user_follow_business" in meta.chamadas[0]["params"]["fields"]


def test_conta_instagram_login_segue_no_graph_instagram(meta):
    db.conn().execute("DELETE FROM accounts")
    db.conn().commit()
    conta = db.upsert_account("IGID-1", "1784", "velha", "IGAA", "2099-01-01T00:00:00Z")
    assert conta["api_modo"] == "instagram_login"
    meta.rotas[("POST", "/messages")] = (200, {})
    meta.rotas[("POST", "/subscribed_apps")] = (200, {})
    instagram.send_text(conta, {"id": "X"}, "oi")
    instagram.subscribe_webhooks(conta)
    instagram.fetch_media_list(conta)
    assert meta.urls() == [f"{IG}/IGID-1/messages", f"{IG}/me/subscribed_apps", f"{IG}/me/media"]


# ---------- webhook ----------

def _assina(secret, corpo):
    return "sha256=" + hmac.new(secret.encode(), corpo, hashlib.sha256).hexdigest()


def test_webhook_assinado_com_secret_do_app_geral(client, modo_fb, monkeypatch):
    from app import flowengine
    recebidos = []
    monkeypatch.setattr(flowengine, "process_payload", recebidos.append)
    corpo = json.dumps({"object": "instagram", "entry": []}).encode()
    assert client.post("/webhook", content=corpo,
                       headers={"X-Hub-Signature-256": _assina("fb-secret", corpo)}).status_code == 200
    assert client.post("/webhook", content=corpo,
                       headers={"X-Hub-Signature-256": _assina("outro", corpo)}).status_code == 403
    assert len(recebidos) == 1


def test_webhook_roteia_pra_conta_certa(modo_fb, meta):
    from app import flowengine
    conta = _conta_fb()
    outra = db.upsert_account("IGID-OUTRA", "17841499999999999", "outra", "IGAA", None)
    payload = {"object": "instagram", "entry": [{
        "id": "17841400000000050", "time": 1,
        "changes": [{"field": "comments", "value": {
            "id": "C77", "text": "nada a ver", "from": {"id": "IGSID5", "username": "fulano"},
            "media": {"id": "M1"}}}]}]}
    flowengine.process_payload(payload)
    linha = db.conn().execute("select account_id from events where kind='sem_keyword' "
                              "order by id desc limit 1").fetchone()
    assert linha[0] == conta["id"] != outra["id"]
    # comentário da própria conta (ID 1784...) não vira evento
    antes = db.conn().execute("select count(*) from events where kind='sem_keyword'").fetchone()[0]
    payload["entry"][0]["changes"][0]["value"].update(id="C78", **{"from": {"id": "17841400000000050"}})
    flowengine.process_payload(payload)
    assert db.conn().execute("select count(*) from events where kind='sem_keyword'").fetchone()[0] == antes


# ---------- refresh e token derrubado ----------

def test_refresh_pulado_no_login_do_facebook(modo_fb, meta):
    from app import main
    conta = db.upsert_account_fb("17841400000000060", "x", "SUAT-6",
                                 db.in_seconds_iso(5 * 86400), "")
    meta.rotas[("GET", "/17841400000000060")] = (200, {"username": "x"})
    main._renovar_tokens()
    assert not any("refresh_access_token" in u for u in meta.urls())
    assert meta.urls() == [f"{FB}/17841400000000060"]
    assert instagram.refresh_token(conta)[0] is False
    assert not db.conn().execute("select 1 from events where kind='token_refresh' and account_id=?",
                                 (conta["id"],)).fetchone()


def test_erro_190_pede_reconectar_no_painel(painel, meta):
    conta = _conta_fb()
    meta.rotas[("POST", "/messages")] = (400, {"error": {
        "message": "Error validating access token", "type": "OAuthException", "code": 190}})
    ok, _, _ = instagram.send_text(conta, {"id": "X"}, "oi")
    assert ok is False and instagram.token_invalido(conta)
    assert instagram.token_status(conta)["valido"] is False
    html = painel.get("/painel").text
    assert "Reconectar conta" in html and "não aceita mais o acesso" in html
    assert instagram.cooldown_restante() == 0          # 190 não é throttle

    # reconectar limpa a marca
    _rotas_unificado(meta, [{"id": "17841400000000050", "username": "loja"}], token="SUAT-NOVO")
    _, q = _comeca(painel)
    painel.get(f"/auth/callback?code=abc&state={q['state'][0]}", follow_redirects=False)
    assert not instagram.token_invalido(db.first_account())


def test_verificacao_periodica_marca_190(modo_fb, meta):
    from app import main
    conta = _conta_fb()
    meta.rotas[("GET", "/17841400000000050")] = (400, {"error": {"code": 190}})
    main._renovar_tokens()
    assert instagram.token_invalido(conta)


def test_190_na_conta_instagram_login_nao_marca(meta):
    db.conn().execute("DELETE FROM accounts")
    db.conn().commit()
    conta = db.upsert_account("IGID-2", "1785", "v", "IGAA", "2099-01-01T00:00:00Z")
    meta.rotas[("POST", "/messages")] = (400, {"error": {"code": 190}})
    instagram.send_text(conta, {"id": "X"}, "oi")
    assert not instagram.token_invalido(conta)


# ---------- configuração ----------

def test_config_salva_login_unificado(painel):
    for k in ("meta_fb_app_id", "meta_fb_app_secret", "meta_fb_config_id"):
        segredos.guardar(k, "")
    db.set_ajuste("meta_login_modo", "")
    r = painel.post("/config", data={"meta_login_modo": "facebook_login", "meta_fb_app_id": "777",
                                     "meta_fb_app_secret": "s3", "meta_fb_config_id": "888"},
                    follow_redirects=False)
    assert r.status_code == 303
    from app import main
    assert main.login_modo() == "facebook_login"
    assert (main.meta_app_id(), main.meta_app_secret(), main.fb_config_id()) == ("777", "s3", "888")
    html = painel.get("/config").text
    assert "Login unificado" in html and 'value="888"' in html and "s3" not in html


def test_modo_padrao_e_o_de_sempre(monkeypatch):
    from app import main
    monkeypatch.delenv("META_LOGIN_MODO", raising=False)
    monkeypatch.delenv("META_FB_APP_ID", raising=False)
    db.set_ajuste("meta_login_modo", "")
    segredos.guardar("meta_fb_app_id", "")
    assert main.login_modo() == "instagram_login"
