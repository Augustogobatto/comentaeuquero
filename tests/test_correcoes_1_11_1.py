"""Correções da 1.11.1 (code review da 1.11.0): ida e volta entre o login unificado e
o login do Instagram, e restos do OAuth pendente.

Meta de mentira, nenhuma chamada sai pra rede.
"""
import json
import time
from urllib.parse import parse_qs, urlparse

import pytest

from app import db, instagram, segredos
from tests.test_login_unificado import MetaFake, _rotas_unificado

BASE = "https://ceq.teste"


@pytest.fixture
def meta(monkeypatch):
    m = MetaFake()
    monkeypatch.setattr(instagram.requests, "get", m.get)
    monkeypatch.setattr(instagram.requests, "post", m.post)
    db.set_ajuste("throttle_until", "")
    return m


@pytest.fixture
def painel(client, monkeypatch):
    """Painel logado, com os dois pares de chave preenchidos e banco sem conta."""
    from app import main
    from tests.conftest import _login
    for v in ("CEQ_ENCRYPTION_KEY", "META_APP_ID", "META_APP_SECRET", "META_LOGIN_MODO",
              "META_FB_APP_ID", "META_FB_APP_SECRET", "META_FB_CONFIG_ID"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(main, "BASE_URL", BASE)
    db.conn().execute("DELETE FROM accounts")
    db.conn().commit()
    segredos.guardar("meta_app_id", "111")
    segredos.guardar("meta_app_secret", "ig-secret")
    segredos.guardar("meta_fb_app_id", "555")
    segredos.guardar("meta_fb_app_secret", "fb-secret")
    segredos.guardar("meta_fb_config_id", "999")
    db.set_ajuste("meta_login_modo", "instagram_login")
    yield _login(client, monkeypatch)
    for k in ("meta_app_id", "meta_app_secret", "meta_fb_app_id", "meta_fb_app_secret",
              "meta_fb_config_id", "oauth_pendente"):
        segredos.guardar(k, "")
    db.set_ajuste("meta_login_modo", "")
    db.conn().execute("DELETE FROM ajustes WHERE chave LIKE 'token_invalido:%'")
    db.conn().commit()


def _rotas_ig(meta, me_id, user_id, username="dono", token="IGAA-NOVO"):
    meta.rotas[("POST", "api.instagram.com/oauth/access_token")] = (
        200, {"access_token": "CURTO", "user_id": user_id, "permissions": ["x"]})
    meta.rotas[("GET", "graph.instagram.com/access_token")] = (
        200, {"access_token": token, "expires_in": 5184000})
    meta.rotas[("GET", "/me")] = (200, {"id": me_id, "user_id": user_id, "username": username})
    meta.rotas[("POST", "/subscribed_apps")] = (200, {"success": True})


def _start(cliente):
    r = cliente.get("/auth/start", follow_redirects=False)
    assert r.status_code in (302, 307)
    return r.headers["location"], parse_qs(urlparse(r.headers["location"]).query)["state"][0]


# ---------- 1. callback do login do Instagram limpa a marca "reconectar" ----------

def test_callback_ig_limpa_marca_de_token_invalido(painel, meta):
    conta = db.upsert_account_fb("17841400000000001", "dono", "SUAT", None, "")
    instagram._confere_token(conta, {"error": {"code": 190}})
    assert instagram.token_invalido(conta)

    _rotas_ig(meta, "17841400000000001", "17841400000000001")
    _, st = _start(painel)
    r = painel.get(f"/auth/callback?code=abc&state={st}", follow_redirects=False)
    assert r.status_code == 303
    nova = db.first_account()
    assert nova["id"] == conta["id"] and nova["api_modo"] == "instagram_login"
    assert not instagram.token_invalido(nova)
    assert "reconectar</span>" not in painel.get("/painel").text


# ---------- 2. upsert_account acha a linha pelo ig_user_id ----------

def test_conta_nascida_no_unificado_volta_pro_ig_na_mesma_linha():
    db.conn().execute("DELETE FROM accounts")
    db.conn().commit()
    fb = db.upsert_account_fb("17841400000000077", "nova", "SUAT", None, "PG1")
    ig = db.upsert_account("APPSCOPED-123", "17841400000000077", "nova", "IGAA",
                           "2099-01-01T00:00:00Z")
    assert db.conn().execute("select count(*) from accounts").fetchone()[0] == 1
    assert ig["id"] == fb["id"]
    assert ig["ig_id"] == "APPSCOPED-123" and ig["ig_user_id"] == "17841400000000077"
    assert ig["access_token"] == "IGAA" and ig["token_expires_at"] == "2099-01-01T00:00:00Z"
    assert ig["api_modo"] == "instagram_login" and ig["page_id"] == ""
    assert db.first_account()["id"] == fb["id"]
    # webhook do login do Instagram chega pelos dois IDs e cai na mesma linha
    assert db.get_account_by_ig_id("APPSCOPED-123")["id"] == fb["id"]
    assert db.get_account_by_ig_id("17841400000000077")["id"] == fb["id"]


def test_volta_pro_ig_preserva_fluxos_e_leads():
    db.conn().execute("DELETE FROM accounts")
    db.conn().commit()
    fb = db.upsert_account_fb("17841400000000078", "nova", "SUAT", None, "")
    db.conn().execute("INSERT INTO leads (account_id, igsid, username) VALUES (?,?,?)",
                      (fb["id"], "IGSID-1", "lead1"))
    db.conn().commit()
    ig = db.upsert_account("APPSCOPED-456", "17841400000000078", "nova", "IGAA",
                           "2099-01-01T00:00:00Z")
    assert ig["id"] == fb["id"]
    n = db.conn().execute("select count(*) from leads where account_id=?",
                          (fb["id"],)).fetchone()[0]
    assert n == 1


def test_conta_ig_antiga_reconecta_na_mesma_linha():
    db.conn().execute("DELETE FROM accounts")
    db.conn().commit()
    a = db.upsert_account("9001", "17841400000000001", "dono", "T1", "2099-01-01T00:00:00Z")
    b = db.upsert_account("9001", "17841400000000001", "dono2", "T2", "2099-02-01T00:00:00Z")
    assert b["id"] == a["id"] and b["access_token"] == "T2" and b["username"] == "dono2"
    assert db.conn().execute("select count(*) from accounts").fetchone()[0] == 1


def test_contas_sem_ig_user_id_nao_se_misturam():
    db.conn().execute("DELETE FROM accounts")
    db.conn().commit()
    a = db.upsert_account("AAA", "", "a", "T1", "2099-01-01T00:00:00Z")
    b = db.upsert_account("BBB", "", "b", "T2", "2099-01-01T00:00:00Z")
    assert a["id"] != b["id"]
    assert db.conn().execute("select count(*) from accounts").fetchone()[0] == 2


def test_linhas_do_login_do_instagram_nao_se_fundem_por_ig_user_id():
    """Comportamento da 1.11.0 mantido: duas linhas no login do Instagram com ig_id
    diferentes continuam duas, mesmo com o mesmo ig_user_id."""
    db.conn().execute("DELETE FROM accounts")
    db.conn().commit()
    a = db.upsert_account("APP-A", "1", "a", "T1", "2099-01-01T00:00:00Z")
    b = db.upsert_account("APP-B", "1", "b", "T2", "2099-01-01T00:00:00Z")
    assert a["id"] != b["id"]
    assert db.get_account(a["id"])["access_token"] == "T1"


def test_ig_id_ja_existente_ganha_da_busca_por_ig_user_id():
    """Se já há uma linha com esse ig_id, ela é a atualizada (como antes) e o UNIQUE
    de ig_id não é violado."""
    db.conn().execute("DELETE FROM accounts")
    db.conn().commit()
    db.upsert_account_fb("17841400000000090", "fb", "SUAT", None, "")
    ig_antiga = db.upsert_account("APP-1", "OUTRO", "ig", "T1", "2099-01-01T00:00:00Z")
    r = db.upsert_account("APP-1", "17841400000000090", "ig", "T2", "2099-01-01T00:00:00Z")
    assert r["id"] == ig_antiga["id"] and r["access_token"] == "T2"


# ---------- 3. OAuth pendente não fica no banco depois do prazo ----------

def _pendente(painel, meta):
    db.set_ajuste("meta_login_modo", "facebook_login")
    _rotas_unificado(meta, [{"id": "17841400000000010", "username": "a"},
                            {"id": "17841400000000020", "username": "b"}], token="SUAT-SEGREDO")
    _, st = _start(painel)
    assert painel.get(f"/auth/callback?code=x&state={st}").status_code == 200
    assert "SUAT-SEGREDO" in segredos.ler("oauth_pendente")
    return st


def test_pendente_vencido_e_apagado_na_escolha(painel, meta):
    st = _pendente(painel, meta)
    p = json.loads(segredos.ler("oauth_pendente"))
    p["ate"] = time.time() - 1
    segredos.guardar("oauth_pendente", json.dumps(p))
    r = painel.post("/auth/escolher", data={"state": st, "ig": "17841400000000010"},
                    follow_redirects=False)
    assert r.status_code == 400 and db.first_account() is None
    assert segredos.ler("oauth_pendente") == ""
    assert "SUAT-SEGREDO" not in (db.get_ajuste("seg:oauth_pendente", "") or "")


def test_pendente_apagado_no_proximo_start(painel, meta):
    _pendente(painel, meta)
    _start(painel)
    assert segredos.ler("oauth_pendente") == ""


def test_pendente_no_prazo_continua_escolhivel(painel, meta):
    st = _pendente(painel, meta)
    r = painel.post("/auth/escolher", data={"state": st, "ig": "17841400000000020"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert db.first_account()["ig_user_id"] == "17841400000000020"


# ---------- 4. o modo vale o da ida, não o da volta ----------

def test_modo_trocado_no_meio_usa_o_da_ida_ig(painel, meta):
    _rotas_ig(meta, "APP-9", "17841400000000099")
    url, st = _start(painel)                       # começou no login do Instagram
    assert url.startswith("https://www.instagram.com/")
    db.set_ajuste("meta_login_modo", "facebook_login")   # trocou em /config no meio
    r = painel.get(f"/auth/callback?code=abc&state={st}", follow_redirects=False)
    assert r.status_code == 303
    conta = db.first_account()
    assert conta["api_modo"] == "instagram_login" and conta["ig_id"] == "APP-9"
    troca = [c for c in meta.chamadas if c["url"].endswith("/oauth/access_token")][0]
    assert troca["corpo"]["client_id"] == "111" and troca["corpo"]["client_secret"] == "ig-secret"


def test_modo_trocado_no_meio_usa_o_da_ida_fb(painel, meta):
    db.set_ajuste("meta_login_modo", "facebook_login")
    _rotas_unificado(meta, [{"id": "17841400000000055", "username": "loja"}])
    url, st = _start(painel)
    assert url.startswith("https://www.facebook.com/")
    db.set_ajuste("meta_login_modo", "instagram_login")
    r = painel.get(f"/auth/callback?code=abc&state={st}", follow_redirects=False)
    assert r.status_code == 303
    conta = db.first_account()
    assert conta["api_modo"] == "facebook_login"
    troca = [c for c in meta.chamadas if c["url"].endswith("/oauth/access_token")][0]
    assert troca["params"]["client_id"] == "555"
    assert troca["params"]["client_secret"] == "fb-secret"


def test_cookie_antigo_sem_modo_cai_no_modo_atual(painel, meta):
    """Quem começou a conexão na 1.11.0 (só o cookie do state) e voltou já na 1.11.1."""
    from app import main
    _rotas_ig(meta, "APP-7", "17841400000000007")
    painel.cookies.set(main.OAUTH_STATE_COOKIE, "st-antigo")
    r = painel.get("/auth/callback?code=abc&state=st-antigo", follow_redirects=False)
    assert r.status_code == 303
    assert db.first_account()["api_modo"] == "instagram_login"
