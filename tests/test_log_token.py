import logging


def _dispara(caplog, path):
    """Mesmo formato que o uvicorn usa no access log."""
    lg = logging.getLogger("uvicorn.access")
    with caplog.at_level(logging.INFO, logger="uvicorn.access"):
        lg.info('%s - "%s %s HTTP/%s" %d', "1.2.3.4:5", "GET", path, "1.1", 200)


def test_token_de_setup_nao_vai_pro_access_log(client, caplog):
    from app.main import instalar_filtro_log
    instalar_filtro_log()  # é o que o startup faz
    assert client.get("/instalar?t=tok-teste").status_code == 200
    _dispara(caplog, "/instalar?t=tok-teste")
    _dispara(caplog, "/instalar?x=1&t=tok-teste&y=2")
    regs = [r for r in caplog.records if r.name == "uvicorn.access"]
    assert len(regs) == 2
    for r in regs:
        assert "tok-teste" not in r.getMessage()
        assert "t=***" in r.getMessage()


def test_startup_instala_o_filtro(monkeypatch):
    import asyncio
    from app import main
    monkeypatch.setattr(main, "check_license", lambda: None)  # sem rede no teste
    lg = logging.getLogger("uvicorn.access")
    lg.removeFilter(main.FILTRO_TOKEN_SETUP)
    asyncio.run(main.startup())
    assert main.FILTRO_TOKEN_SETUP in lg.filters


def test_formulario_manda_token_no_corpo_e_nao_na_url(client):
    html = client.get("/instalar?t=tok-teste").text
    assert 'action="/instalar"' in html
    assert 'name="t" value="tok-teste"' in html
    r = client.post("/instalar", data={"t": "tok-teste", "senha": "Minha senha 123",
                                       "senha2": "Minha senha 123"}, follow_redirects=False)
    assert r.status_code == 303
