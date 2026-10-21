"""Testes que faltavam na revisão cega: cada um pega uma mutação específica."""
import hashlib
import hmac
import json


def _main():
    from app import main
    return main


def test_instalar_404_sem_setup_token_mesmo_com_t(client, monkeypatch):
    monkeypatch.setattr(_main(), "SETUP_TOKEN", "")
    assert client.get("/instalar?t=").status_code == 404
    assert client.get("/instalar?t=tok-teste").status_code == 404
    r = client.post("/instalar", data={"t": "", "senha": "Minha senha 123",
                                       "senha2": "Minha senha 123"})
    assert r.status_code == 404


def test_senha_curta_recusada(client):
    from app import db
    from app.senha import CHAVE_HASH
    r = client.post("/instalar", data={"t": "tok-teste", "senha": "1234567", "senha2": "1234567"})
    assert r.status_code == 200 and "pelo menos 8" in r.text
    assert db.get_ajuste(CHAVE_HASH, "") == ""


def _assina(secret, corpo):
    return "sha256=" + hmac.new(secret.encode(), corpo, hashlib.sha256).hexdigest()


def test_webhook_aceita_assinatura_com_secret_do_painel(client, monkeypatch):
    from app import flowengine, segredos
    monkeypatch.delenv("META_APP_SECRET", raising=False)
    monkeypatch.delenv("CEQ_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(flowengine, "process_payload", lambda p: None)
    segredos.guardar("meta_app_secret", "do-painel")
    corpo = json.dumps({"object": "instagram", "entry": []}).encode()
    ok = client.post("/webhook", content=corpo,
                     headers={"X-Hub-Signature-256": _assina("do-painel", corpo)})
    assert ok.status_code == 200
    assert client.post("/webhook", content=corpo).status_code == 403
    ruim = client.post("/webhook", content=corpo,
                       headers={"X-Hub-Signature-256": _assina("outro", corpo)})
    assert ruim.status_code == 403


def test_env_vence_o_painel(monkeypatch):
    from app import segredos
    monkeypatch.delenv("CEQ_ENCRYPTION_KEY", raising=False)
    segredos.guardar("meta_app_secret", "do-painel")
    segredos.guardar("meta_app_id", "222")
    monkeypatch.setenv("META_APP_SECRET", "do-env")
    monkeypatch.setenv("META_APP_ID", "111")
    m = _main()
    assert m.meta_app_secret() == "do-env" and m.meta_app_id() == "111"


def test_429_depois_de_senhas_erradas_com_senha_em_ajustes(client, monkeypatch):
    m = _main()
    monkeypatch.setattr(m, "LOGIN_TENTATIVAS", {})
    monkeypatch.setattr(m, "LOGIN_FALHAS_GLOBAIS", [])
    m.definir_senha("Minha senha 123")
    assert not m.ADMIN_PASSWORD  # a senha vem de ajustes, não do .env
    for _ in range(m.LOGIN_LIMITE):
        assert client.post("/login", data={"senha": "errada!!"}).status_code == 401
    r = client.post("/login", data={"senha": "Minha senha 123"}, follow_redirects=False)
    assert r.status_code == 429 and "ceq_session" not in r.headers.get("set-cookie", "")


def test_429_pelo_teto_global(client, monkeypatch):
    m = _main()
    monkeypatch.setattr(m, "LOGIN_TENTATIVAS", {})
    monkeypatch.setattr(m, "LOGIN_FALHAS_GLOBAIS", [])
    monkeypatch.setattr(m, "LOGIN_GLOBAL_LIMITE", 3)
    monkeypatch.setattr(m, "LOGIN_LIMITE", 100)  # isola o teto geral do freio por IP
    m.definir_senha("Minha senha 123")
    for _ in range(3):
        assert client.post("/login", data={"senha": "errada!!"}).status_code == 401
    assert client.post("/login", data={"senha": "errada!!"}).status_code == 429


def test_hash_da_senha_pbkdf2_sem_a_senha(client):
    from app import db
    from app.senha import CHAVE_HASH, conferir_senha, definir_senha
    definir_senha("Minha senha 123")
    h = db.get_ajuste(CHAVE_HASH, "")
    assert h.startswith("pbkdf2_sha256$200000$")
    assert "Minha senha 123" not in h
    assert conferir_senha("Minha senha 123") and not conferir_senha("Minha senha 124")
