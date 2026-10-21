import os
def test_cifra_e_decifra(monkeypatch, tmp_path):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("CEQ_ENCRYPTION_KEY", Fernet.generate_key().decode())
    import importlib, app.segredos as s; importlib.reload(s)
    s.guardar("meta_app_secret", "abc123")
    from app import db
    bruto = db.get_ajuste("seg:meta_app_secret", "")
    assert bruto and "abc123" not in bruto
    assert s.ler("meta_app_secret") == "abc123"

def test_config_salva_app_id_e_secret(client):
    # loga primeiro
    from app.main import definir_senha
    definir_senha("Minha senha 123")
    client.post("/login", data={"senha": "Minha senha 123"})
    r = client.post("/config", data={"teto": "", "alerta_token": "", "meta_app_id": "111", "meta_app_secret": "s3gr3d0"}, follow_redirects=False)
    assert r.status_code in (200, 302, 303)
    from app.main import meta_app_id, meta_app_secret
    assert meta_app_id() == "111" and meta_app_secret() == "s3gr3d0"
    pagina = client.get("/config").text
    assert "s3gr3d0" not in pagina


def _s(monkeypatch, chave):
    import importlib, app.segredos as s
    if chave is None:
        monkeypatch.delenv("CEQ_ENCRYPTION_KEY", raising=False)
    else:
        monkeypatch.setenv("CEQ_ENCRYPTION_KEY", chave)
    return importlib.reload(s)


def test_estado_chave_tres_casos(monkeypatch):
    from cryptography.fernet import Fernet
    assert _s(monkeypatch, None).estado_chave() == "ausente"
    assert _s(monkeypatch, "isso-nao-e-fernet").estado_chave() == "invalida"
    s = _s(monkeypatch, Fernet.generate_key().decode())
    assert s.estado_chave() == "ok" and s.cifrado_disponivel() is True


def test_chave_invalida_grava_raw_com_aviso_e_painel_mostra(monkeypatch, caplog, client):
    import logging
    from app import db
    s = _s(monkeypatch, "isso-nao-e-fernet")
    assert s.cifrado_disponivel() is False
    with caplog.at_level(logging.WARNING, logger="ceq.segredos"):
        s.guardar("meta_app_secret", "seg-x")
    assert db.get_ajuste("seg:meta_app_secret", "") == "raw:seg-x"
    assert any("inválida" in r.getMessage() for r in caplog.records)
    from app.main import definir_senha
    definir_senha("Minha senha 123")
    client.post("/login", data={"senha": "Minha senha 123"})
    html = client.get("/config").text
    assert "CEQ_ENCRYPTION_KEY</code> com chave inválida no .env" in html  # aviso no card
    assert "</span>chave inválida</td>" in html                           # linha do ambiente


def test_sem_chave_painel_nao_diz_invalida(monkeypatch, client):
    _s(monkeypatch, None)
    from app.main import definir_senha
    definir_senha("Minha senha 123")
    client.post("/login", data={"senha": "Minha senha 123"})
    assert "chave inválida" not in client.get("/config").text


def test_ler_recifra_valor_em_claro(monkeypatch):
    from cryptography.fernet import Fernet
    from app import db
    db.set_ajuste("seg:meta_app_secret", "raw:antigo")
    s = _s(monkeypatch, Fernet.generate_key().decode())
    assert s.ler("meta_app_secret") == "antigo"
    bruto = db.get_ajuste("seg:meta_app_secret", "")
    assert bruto.startswith("enc:") and "antigo" not in bruto
    assert s.ler("meta_app_secret") == "antigo"
