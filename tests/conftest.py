import os, tempfile, pytest
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="ceq-test-"))
os.environ["ADMIN_PASSWORD"] = ""
os.environ["CEQ_SETUP_TOKEN"] = "tok-teste"
os.environ["CEQ_PERMITE_HTTP"] = "1"
from app import db
db.init()  # as tabelas nascem no startup do app; o TestClient sem `with` não dispara startup

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    db.conn().execute("delete from ajustes where chave='admin_senha_hash'"); db.conn().commit()
    from app.main import app
    return TestClient(app)


# ---------- WhatsApp: nenhuma chamada sai pra Meta de verdade ----------

class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.headers = {"content-type": "application/json"}
        self.text = __import__("json").dumps(body)

    def json(self):
        return self._body


class _MetaWA:
    """Finge a Graph do WhatsApp. `fila(status, body)` enfileira a próxima resposta;
    sem fila, POST devolve um wamid novo (wa_mensagens.wamid é chave primária) e GET
    devolve lista vazia."""

    def __init__(self):
        self.chamadas = []
        self._fila = []
        self._n = 0
        self.ultimo_wamid = ""

    def fila(self, status, body):
        self._fila.append((status, body))

    def _responde(self, metodo):
        if self._fila:
            return _Resp(*self._fila.pop(0))
        if metodo == "GET":
            return _Resp(200, {"data": []})
        self._n += 1
        self.ultimo_wamid = f"wamid.T{self._n}"
        return _Resp(200, {"messages": [{"id": self.ultimo_wamid}]})

    def post(self, url, json=None, params=None, headers=None, timeout=None, **kw):
        self.chamadas.append({"metodo": "POST", "url": url, "json": json, "params": params})
        return self._responde("POST")

    def get(self, url, params=None, headers=None, timeout=None, **kw):
        self.chamadas.append({"metodo": "GET", "url": url, "json": None, "params": params})
        return self._responde("GET")


@pytest.fixture
def meta_wa(monkeypatch):
    from app import whatsapp
    m = _MetaWA()
    monkeypatch.setattr(whatsapp.requests, "post", m.post)
    monkeypatch.setattr(whatsapp.requests, "get", m.get)
    db.set_ajuste("wa_throttle_until", "")
    return m


def _so_esta_conta(conta_id):
    # o CASCADE leva fluxos, leads, sessões e transmissões de testes anteriores
    db.conn().execute("DELETE FROM accounts WHERE id<>?", (conta_id,))
    db.conn().commit()


@pytest.fixture
def conta_wa(monkeypatch):
    import uuid
    from app import segredos, whatsapp
    monkeypatch.delenv("CEQ_ENCRYPTION_KEY", raising=False)
    c = db.upsert_account(uuid.uuid4().hex, "", "conta_wa", "tok-ig", "2099-01-01T00:00:00Z")
    _so_esta_conta(c["id"])
    db.set_wa_config(c["id"], "waba1", "pn1")
    db.update_wa_estado(c["id"], "", "", "", 1000)
    segredos.guardar(whatsapp.chave_token(c["id"]), "tok-wa")
    return db.get_account(c["id"])


def _login(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "LOGIN_TENTATIVAS", {})
    monkeypatch.setattr(main, "LOGIN_FALHAS_GLOBAIS", [])
    main.definir_senha("Minha senha 123")
    r = client.post("/login", data={"senha": "Minha senha 123"}, follow_redirects=False)
    assert r.status_code == 303
    return client


@pytest.fixture
def logado(client, conta_wa, monkeypatch):
    return _login(client, monkeypatch)


@pytest.fixture
def logado_sem_wa(client, monkeypatch):
    import uuid
    c = db.upsert_account(uuid.uuid4().hex, "", "conta_ig", "tok-ig", "2099-01-01T00:00:00Z")
    _so_esta_conta(c["id"])
    return _login(client, monkeypatch)
