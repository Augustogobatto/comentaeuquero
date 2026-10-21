"""Importação de contatos pro WhatsApp: só com consentimento declarado."""
from app import db, main


def test_sem_consentimento_nada_entra(logado, conta_wa):
    antes = db.leads_count(conta_wa["id"])
    r = logado.post("/leads/importar", data={"texto": "Ana, 11 98888-0001"})
    assert r.status_code == 400 and "consentimento" in r.text and db.leads_count(conta_wa["id"]) == antes


def test_texto_com_consentimento(logado, conta_wa):
    r = logado.post("/leads/importar", data={"texto": "Ana, 11 98888-0002\nlixo, 12\nBeto;+55 21 97777-0003", "consentimento": "1", "tag": "importados"})
    assert r.status_code == 200
    l = db.lead_por_wa(conta_wa["id"], "5511988880002")
    assert l["wa_optin_origem"] == "importacao" and db.has_tag(l["id"], "importados")
    assert db.lead_por_wa(conta_wa["id"], "5521977770003")["name"] == "Beto"
    assert "lixo, 12" in r.text


def test_campo_telefone_antigo_so_com_caixa(logado, conta_wa):
    ig = db.touch_lead(conta_wa["id"], "ig-tel"); db.set_field(ig["id"], "telefone", "11966660004")
    logado.post("/leads/importar", data={"consentimento": "1"})
    assert db.get_lead(ig["id"])["wa_id"] == ""
    logado.post("/leads/importar", data={"consentimento": "1", "usar_campo_telefone": "1"})
    l = db.get_lead(ig["id"])
    assert l["wa_id"] == "5511966660004" and l["wa_optin_origem"] == "importacao"


def test_csv(logado, conta_wa):
    csv_ = "nome;telefone\nCaio;(31) 95555-0005\n".encode()
    logado.post("/leads/importar", data={"consentimento": "1"}, files={"arquivo": ("c.csv", csv_, "text/csv")})
    assert db.lead_por_wa(conta_wa["id"], "5531955550005")["name"] == "Caio"


def test_csv_virgula_com_coluna_whatsapp(logado, conta_wa):
    csv_ = "whatsapp,nome\n(31) 95555-0006,Dora\n".encode()
    logado.post("/leads/importar", data={"consentimento": "1"}, files={"arquivo": ("c.csv", csv_, "text/csv")})
    assert db.lead_por_wa(conta_wa["id"], "5531955550006")["name"] == "Dora"


def test_importar_contatos_totais(conta_wa):
    r = main.importar_contatos(conta_wa["id"], [("A", "11 98888-1001"), ("B", "x"), ("C", "11 98888-1001")])
    assert r["importados"] == 2 and r["invalidos"] == ["B, x"]


def test_pagina_e_coluna(logado, conta_wa):
    assert "Tenho consentimento" in logado.get("/leads/importar").text
    assert "Importar contatos" in logado.get("/leads").text


def test_leads_sem_wa_sem_link(logado_sem_wa):
    assert "Importar contatos" not in logado_sem_wa.get("/leads").text


def test_csv_de_uma_linha_sem_sniffer(logado, conta_wa):
    csv_ = "telefone\n31955550007\n".encode()
    logado.post("/leads/importar", data={"consentimento": "1"}, files={"arquivo": ("c.csv", csv_, "text/csv")})
    assert db.lead_por_wa(conta_wa["id"], "5531955550007")["wa_optin_origem"] == "importacao"


def test_importacao_nao_troca_wa_id_que_veio_do_webhook(conta_wa):
    """A Meta entrega pelo wa_id que ela mandou (aqui, conta antiga sem o 9). A planilha
    com o 9 acha o mesmo lead, mas não pode trocar o número por onde ele recebe."""
    from app import wa_webhook
    from tests.wa_helpers import _msg
    wa_webhook.process(_msg("pn1", "551187650099", "Eva", text={"body": "oi"}))
    lead = db.lead_por_wa(conta_wa["id"], "551187650099")
    r = main.importar_contatos(conta_wa["id"], [("Eva", "11 98765-0099")])
    assert r["importados"] == 1
    depois = db.get_lead(lead["id"])
    assert depois["wa_id"] == "551187650099" and depois["wa_optin_origem"]


def test_campo_telefone_nao_troca_wa_id_existente(logado, conta_wa):
    ig = db.touch_lead(conta_wa["id"], "ig-tel-2")
    db.vincular_whatsapp(ig["id"], "5511944440099")
    db.set_field(ig["id"], "telefone", "11933330099")
    logado.post("/leads/importar", data={"consentimento": "1", "usar_campo_telefone": "1"})
    assert db.get_lead(ig["id"])["wa_id"] == "5511944440099"


def test_campo_telefone_mesmo_numero_ganha_optin(logado, conta_wa):
    wa = db.lead_por_wa(conta_wa["id"], "551187650098")
    ig = db.touch_lead(conta_wa["id"], "ig-tel-3")
    db.vincular_whatsapp(ig["id"], "551187650098")
    db.set_field(ig["id"], "telefone", "11 98765-0098")
    logado.post("/leads/importar", data={"consentimento": "1", "usar_campo_telefone": "1"})
    l = db.get_lead(ig["id"])
    assert l["wa_id"] == "551187650098" and l["wa_optin_origem"] == "importacao"
