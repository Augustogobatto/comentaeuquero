def test_instalar_sem_token_e_404(client):
    assert client.get("/instalar").status_code == 404
    assert client.get("/instalar?t=errado").status_code == 404

def test_instalar_define_senha_e_depois_some(client):
    r = client.get("/instalar?t=tok-teste")
    assert r.status_code == 200 and "Crie a senha" in r.text
    r = client.post("/instalar?t=tok-teste", data={"senha": "Minha senha 123", "senha2": "Minha senha 123"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert client.get("/instalar?t=tok-teste").status_code == 404
    r = client.post("/login", data={"senha": "Minha senha 123"}, follow_redirects=False)
    assert r.status_code in (302, 303) and "ceq_session" in r.headers.get("set-cookie", "")

def test_senhas_diferentes_nao_salva(client):
    r = client.post("/instalar?t=tok-teste", data={"senha": "a1234567", "senha2": "b1234567"})
    assert r.status_code == 200 and "não batem" in r.text
