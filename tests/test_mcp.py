"""Servidor MCP: autenticação (token manual e OAuth), cada ferramenta, disparo em
duas etapas, limites e registro. Nada sai pra Meta: o WhatsApp é dublado."""
import base64
import hashlib
import json
import secrets
import shutil
import subprocess
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import anyio
import httpx2
import pytest

from app import db, main, mcp_server, transmissao
from app import mcp_ferramentas as F
from tests.conftest import _login, _so_esta_conta

URL = "http://localhost:8080"


@pytest.fixture(autouse=True)
def _limpo():
    mcp_server._USO.clear()
    F._CODIGOS.clear()
    db.conn().execute("DELETE FROM mcp_tokens")
    db.conn().execute("DELETE FROM mcp_clientes")
    db.conn().commit()
    yield
    mcp_server._USO.clear()


@pytest.fixture
def conta_ig():
    c = db.upsert_account(uuid.uuid4().hex, "", "conta_ig", "tok-ig", "2099-01-01T00:00:00Z")
    _so_esta_conta(c["id"])
    return db.get_account(c["id"])


@pytest.fixture
def token():
    t = "ceq_" + secrets.token_urlsafe(32)
    db.mcp_guardar_token(t, "manual", cliente_nome="token manual")
    return t


def _mcp(token, acao):
    """Roda `acao(cliente)` com o cliente MCP oficial falando HTTP com o app (ASGI)."""
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    async def corre():
        async with mcp_server.rodando():
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=main.app), base_url=URL,
                                          headers={"Authorization": f"Bearer {token}"}) as http:
                async with Client(streamable_http_client(URL + "/mcp", http_client=http)) as c:
                    return await acao(c)
    return anyio.run(corre)


def _chama(token, nome, args=None):
    async def acao(c):
        return await c.call_tool(nome, args or {})
    return _mcp(token, acao)


def _http(metodo, caminho, **kw):
    async def corre():
        async with mcp_server.rodando():
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=main.app),
                                          base_url=URL) as http:
                return await http.request(metodo, caminho, **kw)
    return anyio.run(corre)


# ---------- autenticação ----------

def test_sem_token_401_com_metadados(conta_ig):
    r = _http("POST", "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401
    assert "resource_metadata=" in r.headers["www-authenticate"]
    meta = _http("GET", "/.well-known/oauth-protected-resource/mcp").json()
    assert meta["resource"].endswith("/mcp")
    asm = _http("GET", "/.well-known/oauth-authorization-server").json()
    assert asm["registration_endpoint"].endswith("/register")
    assert "S256" in asm["code_challenge_methods_supported"]


def test_token_errado_e_revogado_401(conta_ig, token):
    r = _http("POST", "/mcp", headers={"Authorization": "Bearer ceq_errado"},
              json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401
    assert not _chama(token, "listar_fluxos").is_error
    db.mcp_apagar_tokens(["manual"])
    with pytest.raises(BaseException):
        _chama(token, "listar_fluxos")


def test_token_guardado_so_em_hash(token):
    linhas = [dict(r) for r in db.conn().execute("SELECT * FROM mcp_tokens")]
    assert linhas and token not in json.dumps(linhas)
    assert linhas[0]["hash"] == hashlib.sha256(token.encode()).hexdigest()


def test_http_sem_criptografia_recusado(conta_ig, token, monkeypatch):
    monkeypatch.setattr(main, "PERMITE_HTTP", False)
    monkeypatch.setattr(main, "COOKIE_SEGURO", True)

    async def corre():
        async with mcp_server.rodando():
            t = httpx2.ASGITransport(app=main.app, client=("203.0.113.5", 1234))
            async with httpx2.AsyncClient(transport=t, base_url="http://exemplo.com") as http:
                return await http.post("/mcp", json={}, headers={"Authorization": f"Bearer {token}"})
    assert anyio.run(corre).status_code == 403


def test_falhas_de_autenticacao_travam_o_ip(conta_ig, monkeypatch):
    monkeypatch.setattr(mcp_server._Porta, "FALHAS_MAX", 3)

    async def corre():
        async with mcp_server.rodando():
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=main.app), base_url=URL) as http:
                return [(await http.post("/mcp", json={}, headers={"Authorization": "Bearer x"})).status_code
                        for _ in range(4)]
    assert anyio.run(corre) == [401, 401, 401, 429]


def _pkce():
    verificador = secrets.token_urlsafe(48)
    desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    return verificador, desafio


def test_oauth_completo_com_login_do_painel(client, conta_ig, monkeypatch):
    monkeypatch.setattr(main, "startup", _nada)
    with client:   # sobe o ciclo de vida: o transporte do MCP
        reg = client.post("/register", json={"client_name": "Claude", "redirect_uris": [
            "https://claude.ai/api/mcp/auth_callback"], "token_endpoint_auth_method": "none"})
        assert reg.status_code == 201, reg.text
        cid = reg.json()["client_id"]
        verificador, desafio = _pkce()
        r = client.get("/authorize", params={
            "response_type": "code", "client_id": cid, "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
            "code_challenge": desafio, "code_challenge_method": "S256", "state": "xyz",
            "resource": URL + "/mcp"}, follow_redirects=False)
        assert r.status_code in (302, 303, 307), r.text
        consent = urlparse(r.headers["location"])
        caminho = consent.path + "?" + consent.query
        # sem login: vai pro login e volta pra tela de permitir
        r = client.get(caminho, follow_redirects=False)
        assert r.headers["location"].startswith("/login?proximo=")
        _login(client, monkeypatch)
        tela = client.get(caminho)
        assert "Permitir acesso?" in tela.text and "claude.ai" in tela.text
        assert tela.headers["x-frame-options"] == "DENY"
        pedido = parse_qs(consent.query)["pedido"][0]
        csrf = tela.text.split('name="csrf" value="')[1].split('"')[0]
        # csrf errado não passa
        assert client.post("/mcp/autorizar", data={"pedido": pedido, "csrf": "x", "decisao": "permitir"},
                           follow_redirects=False).status_code == 400
        r = client.post("/mcp/autorizar", data={"pedido": pedido, "csrf": csrf, "decisao": "permitir"},
                        follow_redirects=False)
        volta = parse_qs(urlparse(r.headers["location"]).query)
        assert volta["state"] == ["xyz"]
        codigo = volta["code"][0]
        # verificador errado: PKCE recusa
        ruim = client.post("/token", data={"grant_type": "authorization_code", "code": codigo, "client_id": cid,
                                           "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                                           "code_verifier": "errado" * 8})
        assert ruim.status_code == 400
        tok = client.post("/token", data={"grant_type": "authorization_code", "code": codigo, "client_id": cid,
                                          "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                                          "code_verifier": verificador})
        assert tok.status_code == 200, tok.text
        acesso, renovacao = tok.json()["access_token"], tok.json()["refresh_token"]
        # código é de uso único
        assert client.post("/token", data={"grant_type": "authorization_code", "code": codigo, "client_id": cid,
                                           "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                                           "code_verifier": verificador}).status_code == 400
        r = client.post("/mcp", headers={"Authorization": f"Bearer {acesso}",
                                         "Accept": "application/json, text/event-stream"},
                        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                            "protocolVersion": "2025-06-18", "capabilities": {},
                            "clientInfo": {"name": "t", "version": "1"}}})
        assert r.status_code == 200, r.text
        # renovação gira o token: o antigo não serve de novo
        nova = client.post("/token", data={"grant_type": "refresh_token", "refresh_token": renovacao,
                                           "client_id": cid})
        assert nova.status_code == 200
        assert client.post("/token", data={"grant_type": "refresh_token", "refresh_token": renovacao,
                                           "client_id": cid}).status_code == 400
        # aparece em Configurações e pode ser desconectado
        assert "Claude" in client.get("/config").text
        client.post("/config/mcp/revogar", data={"cliente_id": cid})
        assert db.mcp_token(nova.json()["access_token"]) is None


async def _nada():
    return None


def test_registro_recusa_redirect_http_externo(client, monkeypatch):
    monkeypatch.setattr(main, "startup", _nada)
    with client:
        r = client.post("/register", json={"client_name": "x", "redirect_uris": ["http://mal.example/cb"],
                                           "token_endpoint_auth_method": "none"})
        assert r.status_code == 400


def test_teto_de_clientes_libera_registro_abandonado(client, monkeypatch):
    monkeypatch.setattr(main, "startup", _nada)
    monkeypatch.setattr(mcp_server, "MAX_CLIENTES", 1)
    corpo = {"client_name": "x", "redirect_uris": ["https://claude.ai/cb"], "token_endpoint_auth_method": "none"}
    with client:
        assert client.post("/register", json=corpo).status_code == 201
        assert client.post("/register", json=corpo).status_code == 400   # teto
        db.conn().execute("UPDATE mcp_clientes SET criado_em='2000-01-01T00:00:00Z'")
        db.conn().commit()
        assert client.post("/register", json=corpo).status_code == 201   # abandonado saiu


def test_login_proximo_nao_vira_redirecionador(client, monkeypatch):
    monkeypatch.setattr(main, "LOGIN_TENTATIVAS", {})
    monkeypatch.setattr(main, "LOGIN_FALHAS_GLOBAIS", [])
    main.definir_senha("Minha senha 123")
    r = client.post("/login", data={"senha": "Minha senha 123", "proximo": "https://mal.example"},
                    follow_redirects=False)
    assert r.headers["location"] == "/painel"
    assert mcp_server.proximo_seguro("/mcp/autorizar?pedido=" + "a" * 32).startswith("/mcp/autorizar")
    assert mcp_server.proximo_seguro("//mal.example/mcp/autorizar") == "/painel"


def test_config_gera_token_uma_vez_e_revoga(client, conta_ig, monkeypatch):
    _login(client, monkeypatch)
    pagina = client.get("/config").text
    assert "Conectar ao Claude (MCP)" in pagina and "/mcp" in pagina
    r = client.post("/config/mcp/token")
    novo = r.text.split('id="mcp-token"')[0].rsplit('value="', 1)[1].split('"')[0]
    assert novo.startswith("ceq_") and db.mcp_token(novo)
    assert novo not in client.get("/config").text   # não aparece de novo
    client.post("/config/mcp/revogar")
    assert db.mcp_token(novo) is None


# ---------- ferramentas pelo transporte ----------

def test_lista_de_ferramentas_e_esquemas_estritos(conta_ig, token):
    async def acao(c):
        return (await c.list_tools()).tools, (await c.list_prompts()).prompts
    ferramentas, prompts = _mcp(token, acao)
    nomes = {t.name for t in ferramentas}
    assert nomes == {"resumo", "listar_fluxos", "ver_fluxo", "listar_leads", "ver_lead",
                     "listar_templates_whatsapp", "listar_transmissoes", "ver_transmissao",
                     "estado_da_conta", "criar_fluxo", "editar_mensagem_do_fluxo",
                     "ligar_desligar_fluxo", "adicionar_gatilho", "etiquetar_lead",
                     "criar_template_whatsapp", "criar_transmissao", "disparar_transmissao"}
    for t in ferramentas:
        assert t.input_schema.get("additionalProperties") is False, t.name
        assert t.description, t.name
    disparar = next(t for t in ferramentas if t.name == "disparar_transmissao")
    assert disparar.annotations.destructive_hint is True
    assert next(t for t in ferramentas if t.name == "resumo").annotations.read_only_hint is True
    assert [p.name for p in prompts] == ["montar_fluxo_de_lancamento"]
    r = _chama(token, "listar_fluxos", {"inventado": 1})
    assert r.is_error


def test_chamada_vira_evento_sem_argumentos(conta_ig, token):
    _chama(token, "criar_fluxo", {"nome": "Ebook segredo", "gatilho": {"tipo": "comentario", "palavras": ["ebook"]},
                                  "passos": [{"tipo": "mensagem", "texto": "texto-secreto-xyz"}]})
    _chama(token, "ver_fluxo", {"fluxo_id": 999999})
    ev = [dict(r) for r in db.conn().execute(
        "SELECT * FROM events WHERE kind='mcp_ferramenta' ORDER BY id DESC LIMIT 2")]
    assert [json.loads(e["payload"])["resultado"] for e in ev] == ["erro", "ok"]
    assert all("texto-secreto" not in e["payload"] and token not in e["payload"] for e in ev)
    assert all(e["ok"] is None for e in ev)   # não entra nas "falhas" do painel


def test_limite_de_chamadas(conta_ig, token, monkeypatch):
    monkeypatch.setitem(mcp_server.LIMITES, "leitura", (2, 60))

    async def acao(c):
        return [(await c.call_tool("listar_fluxos", {})).is_error for _ in range(3)]
    assert _mcp(token, acao) == [False, False, True]


def test_criar_fluxo_pelo_mcp_abre_no_editor(client, conta_ig, token, monkeypatch):
    r = _chama(token, "criar_fluxo", {
        "nome": "Ebook", "gatilho": {"tipo": "comentario", "palavras": ["ebook"],
                                     "respostas_publicas": ["Te mandei no direct!"]},
        "passos": [{"tipo": "mensagem", "texto": "Oi {primeiro_nome}!", "variacoes": ["Olá!"]},
                   {"tipo": "mensagem", "texto": "Quer o ebook?", "botoes": [{"titulo": "Quero"}, {"titulo": "Site", "link": "https://exemplo.com"}]},
                   {"tipo": "pergunta", "texto": "Seu e-mail?", "guardar_em": "email", "espera": "email"},
                   {"tipo": "etiqueta", "adicionar": ["ebook"]},
                   {"tipo": "esperar", "minutos": 5},
                   {"tipo": "link", "texto": "Aqui está", "url": "https://exemplo.com/ebook"}]})
    assert not r.is_error, r.content
    saida = r.structured_content
    assert saida["ligado"] is False and saida["avisos"] == []
    f = db.get_flow(saida["id"])
    tipos = [n["type"] for n in f["graph"]["nodes"]]
    assert tipos == ["text", "buttons", "text", "wait_input", "action", "delay", "buttons"]
    assert all(isinstance(n["position"]["x"], int) for n in f["graph"]["nodes"])
    botao = next(e for e in f["graph"]["edges"] if e["source"] == "n2")
    assert botao["sourceHandle"] == "quero"
    t = db.list_triggers(f["id"])[0]
    assert t["type"] == "comment" and t["keywords"] == ["ebook"]
    _login(client, monkeypatch)
    assert client.get(f"/api/flows/{f['id']}").json()["avisos"] == []


# ---------- ferramentas direto ----------

def test_criar_fluxo_validacoes(conta_ig):
    F.criar_fluxo("Um", {"tipo": "direct", "palavras": ["oi"]}, [{"tipo": "mensagem", "texto": "oi"}])
    with pytest.raises(F.ErroFerramenta, match="Já existe"):
        F.criar_fluxo("um", {"tipo": "direct", "palavras": []}, [{"tipo": "mensagem", "texto": "x"}])
    with pytest.raises(F.ErroFerramenta, match="WhatsApp"):
        F.criar_fluxo("Dois", {"tipo": "direct", "palavras": ["z"]}, [{"tipo": "pedir_whatsapp"}])
    with pytest.raises(F.ErroFerramenta, match="Link inválido"):
        F.criar_fluxo("Tres", {"tipo": "direct", "palavras": ["z"]},
                      [{"tipo": "link", "texto": "x", "url": "javascript:alert(1)"}])
    r = F.criar_fluxo("Quatro", {"tipo": "direct", "palavras": ["OI"]}, [{"tipo": "mensagem", "texto": "x"}],
                      ligar=True)
    assert r["ligado"] is True
    r = F.criar_fluxo("Cinco", {"tipo": "comentario", "palavras": []}, [{"tipo": "mensagem", "texto": "x"}])
    assert any("QUALQUER" in a for a in r["avisos"])


def test_palavra_repetida_avisa(conta_ig):
    F.criar_fluxo("A", {"tipo": "comentario", "palavras": ["promo"]}, [{"tipo": "mensagem", "texto": "x"}], ligar=True)
    r = F.criar_fluxo("B", {"tipo": "comentario", "palavras": ["Promo"]}, [{"tipo": "mensagem", "texto": "y"}])
    assert any("'A'" in a for a in r["avisos"])


def test_editar_ligar_gatilho_e_ver(conta_ig):
    fid = F.criar_fluxo("Mentoria", {"tipo": "comentario", "palavras": ["mentoria"]},
                        [{"tipo": "mensagem", "texto": "v1"}, {"tipo": "esperar", "minutos": 2}])["id"]
    F.editar_mensagem_do_fluxo(fid, "n1", texto="v2", variacoes=["v2b"], link="https://ex.com")
    no = db.get_flow(fid)["graph"]["nodes"][0]["data"]
    assert no == {"text": "v2", "variants": ["v2b"], "link": "https://ex.com"}
    with pytest.raises(F.ErroFerramenta, match="sem texto"):
        F.editar_mensagem_do_fluxo(fid, "n2", texto="x")
    with pytest.raises(F.ErroFerramenta, match="não existe"):
        F.editar_mensagem_do_fluxo(fid, "n9", texto="x")
    F.ligar_desligar_fluxo(fid, True)
    assert db.get_flow(fid)["active"] == 1
    F.adicionar_gatilho(fid, "story", ["mentoria"])
    assert [t["type"] for t in db.list_triggers(fid)] == ["comment", "story_reply"]
    lead = db.touch_lead(conta_ig["id"], "ig-1", "mentoria", "fulana")
    db.log_event("fluxo_inicio", conta_ig["id"], "Mentoria", "comment", True, "fulana", {"flow_id": fid})
    db.log_event("fluxo_envio", conta_ig["id"], "Mentoria", "text", True, "fulana", {"node": "n1"})
    v = F.ver_fluxo(fid)
    assert v["passos"][0]["enviados"] == 1 and v["funil_total"]["acionaram"] == 1
    assert v["abrir_no_editor"].endswith(f"/editor?f={fid}")
    lista = F.listar_fluxos()
    assert lista["fluxos"][0]["gatilhos"][1]["tipo"] == "story"
    res = F.resumo("hoje", fluxo="mentoria")
    assert res["fluxo"] == "Mentoria" and res["pessoas_que_acionaram"] == 1
    assert res["por_origem"] == [{"origem": "comment", "pessoas": 1}]
    assert res["leads_novos"] == 1
    with pytest.raises(F.ErroFerramenta):
        F.resumo("hoje", fluxo="nao-existe")
    assert lead


def test_leads_filtros_paginacao_e_etiqueta(conta_ig):
    ids = []
    for i in range(5):
        ids.append(db.touch_lead(conta_ig["id"], f"p{i}", "ebook" if i % 2 else "aula", f"pessoa{i}")["id"])
    F.etiquetar_lead(ids[0], adicionar=["comprador", "vip"])
    F.etiquetar_lead(ids[0], remover=["vip"])
    assert db.lead_tags(ids[0]) == ["comprador"]
    assert [l["id"] for l in F.listar_leads(etiqueta="comprador")["leads"]] == [ids[0]]
    assert len(F.listar_leads(palavra="ebook")["leads"]) == 2
    p1 = F.listar_leads(por_pagina=2)
    p3 = F.listar_leads(por_pagina=2, pagina=3)
    assert p1["tem_mais"] and not p3["tem_mais"] and len(p3["leads"]) == 1
    assert F.listar_leads(busca="pessoa3")["leads"][0]["username"] == "pessoa3"
    assert len(F.listar_leads(periodo="hoje")["leads"]) == 5
    assert F.listar_leads(desde="2000-01-01", ate="2000-01-02")["leads"] == []
    v = F.ver_lead(username="@pessoa0")
    assert v["etiquetas"] == ["comprador"] and "historico" in v
    with pytest.raises(F.ErroFerramenta):
        F.ver_lead(lead_id=99999999)
    with pytest.raises(F.ErroFerramenta):
        F.etiquetar_lead(ids[0])


def test_estado_da_conta_sem_segredo(conta_ig, monkeypatch):
    monkeypatch.setattr(main, "meta_app_secret", lambda: "segredo-meta-123")
    e = F.estado_da_conta()
    assert e["instagram_conectado"] and e["chave_secreta_meta_configurada"] is True
    assert "segredo-meta-123" not in json.dumps(e) and "tok-ig" not in json.dumps(e)


def test_whatsapp_desligado_da_erro_claro(conta_ig):
    for fn in (F.listar_transmissoes, F.listar_templates_whatsapp):
        with pytest.raises(F.ErroFerramenta, match="WhatsApp"):
            fn()


def _template(conta, nome="black", status="APPROVED", corpo="Oi {{1}}, promo!"):
    db.salvar_templates(conta["id"], [{"name": nome, "language": "pt_BR", "category": "MARKETING",
                                       "status": status, "components": [{"type": "BODY", "text": corpo}]}])


def _optin(conta, n, tag):
    for i in range(n):
        l = db.lead_por_wa(conta["id"], f"5511977{uuid.uuid4().int % 10**6:06d}", f"Pessoa {i}")
        db.registrar_optin(l["id"], "conversa")
        db.add_tag(l["id"], tag)


def test_templates_e_criar_template(conta_wa, meta_wa):
    _template(conta_wa)
    lista = F.listar_templates_whatsapp()
    assert lista["templates"][0]["variaveis"] == ["1"]
    meta_wa.fila(200, {"id": "1", "status": "PENDING"})
    r = F.criar_template_whatsapp("aviso_novo", "UTILITY", "Seu pedido {{1}} saiu", ["123"])
    assert r["status_na_meta"] == "PENDING"
    with pytest.raises(F.ErroFerramenta, match="exemplo"):
        F.criar_template_whatsapp("outro", "UTILITY", "Oi {{1}}", [])


def test_transmissao_rascunho_nao_sai_e_disparo_em_duas_etapas(conta_wa, meta_wa):
    _template(conta_wa)
    _optin(conta_wa, 3, "comprador")
    with pytest.raises(F.ErroFerramenta, match="faltou valor"):
        F.criar_transmissao("BF", "black", "etiqueta", "comprador")
    r = F.criar_transmissao("BF", "black", "etiqueta", "comprador", variaveis={"1": "{primeiro_nome}"})
    tid = r["id"]
    assert r["status"] == "rascunho" and r["publico_previsto"] == 3
    # o worker não toca rascunho
    transmissao.tick(agora=1000.0)
    assert db.get_transmissao(tid)["status"] == "rascunho" and not meta_wa.chamadas
    assert F.listar_transmissoes()["transmissoes"][0]["status"] == "rascunho"
    assert F.ver_transmissao(tid)["publico_previsto_agora"] == 3
    previa = F.disparar_transmissao(tid, quem="manual")
    assert previa["etapa"] == "previa" and previa["pessoas"] == 3
    assert previa["custo_estimado_usd"] == round(3 * transmissao.preco("marketing"), 2)
    assert "Oi {{1}}" in previa["texto_do_template"]
    assert db.get_transmissao(tid)["status"] == "rascunho"
    with pytest.raises(F.ErroFerramenta, match="inválido"):
        F.disparar_transmissao(tid, "ZZZZZZ", quem="manual")
    # código de outro acesso não vale
    with pytest.raises(F.ErroFerramenta, match="inválido"):
        F.disparar_transmissao(tid, previa["codigo_confirmacao"], quem="outro-cliente")
    previa = F.disparar_transmissao(tid, quem="manual")
    # público cresceu depois da prévia: pede prévia nova
    _optin(conta_wa, 1, "comprador")
    with pytest.raises(F.ErroFerramenta, match="cresceu"):
        F.disparar_transmissao(tid, previa["codigo_confirmacao"], quem="manual")
    previa = F.disparar_transmissao(tid, quem="manual")
    ok = F.disparar_transmissao(tid, previa["codigo_confirmacao"], quem="manual")
    assert ok["etapa"] == "disparada" and db.get_transmissao(tid)["status"] == "agendada"
    with pytest.raises(F.ErroFerramenta, match="só rascunho"):
        F.disparar_transmissao(tid, previa["codigo_confirmacao"], quem="manual")
    transmissao.tick(agora=2000.0)
    assert db.get_transmissao(tid)["status"] == "enviando" and meta_wa.chamadas


def test_codigo_de_confirmacao_vence(conta_wa, meta_wa, monkeypatch):
    _template(conta_wa)
    _optin(conta_wa, 1, "v")
    tid = F.criar_transmissao("T", "black", "etiqueta", "v", variaveis={"1": "x"})["id"]
    previa = F.disparar_transmissao(tid, quem="manual")
    F._CODIGOS[previa["codigo_confirmacao"]]["expira"] = 0
    with pytest.raises(F.ErroFerramenta, match="vencido"):
        F.disparar_transmissao(tid, previa["codigo_confirmacao"], quem="manual")


def test_transmissao_template_nao_aprovado(conta_wa):
    _template(conta_wa, nome="pendente", status="PENDING")
    with pytest.raises(F.ErroFerramenta, match="APPROVED"):
        F.criar_transmissao("T", "pendente", variaveis={"1": "x"})


def test_painel_dispara_rascunho(logado, meta_wa):
    conta = db.first_account()
    _template(conta)
    _optin(conta, 1, "p")
    tid = F.criar_transmissao("T", "black", "etiqueta", "p", variaveis={"1": "x"})["id"]
    assert "Disparar" in logado.get(f"/transmissoes/{tid}").text
    logado.post(f"/transmissoes/{tid}/disparar")
    assert db.get_transmissao(tid)["status"] == "agendada"


# ---------- editor: fluxo sem position ----------

def test_api_da_posicao_a_no_sem_position(client, conta_ig, monkeypatch):
    fid = db.create_flow(conta_ig["id"], name="Script", entry_node="a", graph={
        "nodes": [{"id": "b", "type": "text", "data": {"text": "2"}},
                  {"id": "a", "type": "text", "data": {"text": "1"}},
                  {"id": "c", "type": "text", "data": {"text": "3"}, "position": {"x": 1, "y": 2}}],
        "edges": [{"id": "e1", "source": "a", "target": "b"}, {"id": "e2", "source": "b", "target": "c"}]})
    _login(client, monkeypatch)
    nos = {n["id"]: n["position"] for n in client.get(f"/api/flows/{fid}").json()["graph"]["nodes"]}
    assert nos == {"a": {"x": 380, "y": 160}, "b": {"x": 680, "y": 160}, "c": {"x": 1, "y": 2}}


@pytest.mark.skipif(not shutil.which("node"), reason="sem node na máquina")
def test_editor_layout_js():
    teste = Path(__file__).resolve().parent.parent / "editor" / "src" / "layout.test.mjs"
    r = subprocess.run(["node", "--test", str(teste)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
