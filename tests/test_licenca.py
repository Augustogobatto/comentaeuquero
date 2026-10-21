def test_inst_token_usa_ping_do_chao(monkeypatch):
    import importlib
    monkeypatch.setenv("CLUB_TOKEN", "inst_abc")
    from app import main; importlib.reload(main)
    chamadas = []
    class R:  # resposta fake
        def json(self): return {"ok": True, "ativa": True, "membro": "Teste", "estado_desejado": {}}
    def post(url, json=None, timeout=15):
        chamadas.append((url, json)); return R()
    monkeypatch.setattr("requests.post", post)
    main.check_license()
    assert chamadas[0][0].endswith("/api/chao/ping")
    assert chamadas[0][1]["token"] == "inst_abc" and "versao_chao" in chamadas[0][1]
    assert main.LICENSE["status"] == "ativada" and main.LICENSE["member"] == "Teste"

def test_backup_db_so_dono(client):
    assert client.get("/api/backup.db").status_code in (401, 403)
    from app.main import definir_senha
    definir_senha("Minha senha 123"); client.post("/login", data={"senha": "Minha senha 123"})
    r = client.get("/api/backup.db")
    assert r.status_code == 200 and r.content[:15] == b"SQLite format 3"


def test_club_token_usa_validate_antigo(monkeypatch):
    import importlib
    monkeypatch.setenv("CLUB_TOKEN", "club_abc")
    from app import main; importlib.reload(main)
    chamadas = []
    class R:
        def json(self): return {"active": True, "member": "X"}
    def post(url, json=None, timeout=15):
        chamadas.append((url, json)); return R()
    monkeypatch.setattr("requests.post", post)
    main.check_license()
    url, corpo = chamadas[0]
    assert url == main.ACTIVATION_URL
    assert corpo["token"] == "club_abc"
    assert corpo["produto"] == "ceq" and corpo["versao"] == main.VERSAO
    assert corpo["instancia"]
    assert main.LICENSE["status"] == "ativada" and main.LICENSE["member"] == "X"


def _baixa_backup(client):
    from app.main import definir_senha
    definir_senha("Minha senha 123")
    client.post("/login", data={"senha": "Minha senha 123"})
    return client.get("/api/backup.db")


def test_backup_nao_leva_sessao_do_painel(client, tmp_path):
    import sqlite3
    from app import db
    r = _baixa_backup(client)
    assert r.status_code == 200
    # a sessão existe no banco vivo...
    assert db.conn().execute("select count(*) from painel_sessions").fetchone()[0] >= 1
    arq = tmp_path / "b.db"; arq.write_bytes(r.content)
    # ...mas não no arquivo baixado
    assert sqlite3.connect(arq).execute("select count(*) from painel_sessions").fetchone()[0] == 0


def test_backup_apaga_tmp_se_falhar(client, monkeypatch, tmp_path):
    import tempfile
    from app import db
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    def explode(*a, **k): raise RuntimeError("falhou no meio")
    monkeypatch.setattr(db, "log_event", explode)
    import pytest
    with pytest.raises(RuntimeError):
        _baixa_backup(client)
    assert list(tmp_path.glob("ceq-backup-*")) == []


def test_config_avisa_que_backup_nao_leva_env(client):
    from app.main import definir_senha
    definir_senha("Minha senha 123")
    client.post("/login", data={"senha": "Minha senha 123"})
    html = client.get("/config").text
    assert "/api/backup.db" in html
    assert ("O backup não leva o .env: guarde a sua CEQ_ENCRYPTION_KEY, ou cole a chave "
            "secreta da Meta de novo ao restaurar.") in html
