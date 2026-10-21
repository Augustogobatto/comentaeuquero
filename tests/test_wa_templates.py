"""Templates do WhatsApp: sincronizar da Meta, listar, criar."""
from app import api, db

TPL = {"name": "boas_vindas", "language": "pt_BR", "category": "MARKETING", "status": "APPROVED",
       "components": [{"type": "BODY", "text": "Oi {{1}}, seu cupom é {{2}}"},
                      {"type": "BUTTONS", "buttons": [{"type": "QUICK_REPLY", "text": "Quero"}]}]}


def test_sync_grava_e_apaga_o_que_sumiu(conta_wa, meta_wa, logado):
    meta_wa.fila(200, {"data": [TPL, {**TPL, "name": "velho"}]})
    assert logado.post("/api/wa/templates/sync").json() == {"total": 2}
    meta_wa.fila(200, {"data": [TPL]})
    logado.post("/api/wa/templates/sync")
    lista = logado.get("/api/wa/templates").json()
    assert [t["nome"] for t in lista] == ["boas_vindas"]
    assert lista[0]["variaveis"] == ["1", "2"] and lista[0]["botoes"] == ["Quero"]


def test_lista_so_aprovados(conta_wa, meta_wa, logado):
    meta_wa.fila(200, {"data": [TPL, {**TPL, "name": "pendente", "status": "PENDING"}]})
    logado.post("/api/wa/templates/sync")
    assert [t["nome"] for t in logado.get("/api/wa/templates?aprovados=1").json()] == ["boas_vindas"]


def test_criar_valida_nome_e_exemplos(conta_wa, meta_wa, logado):
    r = logado.post("/api/wa/templates", json={"nome": "Com Espaço", "categoria": "MARKETING", "corpo": "oi"})
    assert r.status_code == 400
    r = logado.post("/api/wa/templates", json={"nome": "promo", "categoria": "MARKETING", "corpo": "Oi {{1}}", "exemplos": []})
    assert r.status_code == 400 and meta_wa.chamadas == []


def test_criar_manda_pra_meta(conta_wa, meta_wa, logado):
    meta_wa.fila(200, {"id": "t1", "status": "PENDING", "category": "MARKETING"})
    meta_wa.fila(200, {"data": []})
    r = logado.post("/api/wa/templates", json={"nome": "promo", "categoria": "MARKETING", "corpo": "Oi {{1}}", "exemplos": ["Ana"], "botoes": ["Quero"]})
    assert r.status_code == 200 and r.json()["status"] == "PENDING"
    c = meta_wa.chamadas[0]
    assert c["url"].endswith("/waba1/message_templates") and c["json"]["components"][0]["example"] == {"body_text": [["Ana"]]}


def test_erro_da_meta_vira_400_com_mensagem(conta_wa, meta_wa, logado):
    meta_wa.fila(400, {"error": {"code": 100, "message": "Nome já existe"}})
    r = logado.post("/api/wa/templates", json={"nome": "promo", "categoria": "UTILITY", "corpo": "oi"})
    assert r.status_code == 400 and "Nome já existe" in r.text and "tok-wa" not in r.text


def test_pagina_templates(conta_wa, logado):
    assert "Quem aprova é a Meta" in logado.get("/templates").text


def test_sem_wa_configurado_400(client, logado_sem_wa):
    assert logado_sem_wa.post("/api/wa/templates/sync").status_code == 400


def test_variaveis_e_botoes_do_template():
    tpl = {"componentes": TPL["components"]}
    assert api.variaveis_do_template(tpl) == ["1", "2"] and api.botoes_do_template(tpl) == ["Quero"]


def test_sync_com_erro_da_meta_nao_apaga_nada(conta_wa, meta_wa):
    db.salvar_templates(conta_wa["id"], [TPL])
    meta_wa.fila(500, {"error": {"code": 1, "message": "erro temporario"}})
    meta_wa.fila(500, {"error": {"code": 1, "message": "erro temporario"}})
    api.sincronizar_templates(conta_wa)
    assert [t["nome"] for t in db.listar_templates(conta_wa["id"])] == ["boas_vindas"]
