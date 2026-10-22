"""Pastas, busca e sync automático dos templates; erros e custo da transmissão."""
import re

import pytest

from app import api, db, mcp_ferramentas as F, transmissao
from tests.test_wa_transmissao import _leads


def _tpl(nome, status="APPROVED", idioma="pt_BR", corpo="Oi {{1}}"):
    return {"name": nome, "language": idioma, "category": "MARKETING", "status": status,
            "components": [{"type": "BODY", "text": corpo}]}


@pytest.fixture
def sem_cooldown(conta_wa):
    db.set_ajuste(f"wa_tpl_autosync:{conta_wa['id']}", "0")


def _pasta_de(conta, nome):
    return next(t["pasta"] for t in db.listar_templates(conta["id"]) if t["nome"] == nome)


def test_crud_de_pasta(conta_wa, logado):
    r = logado.post("/api/wa/pastas", json={"nome": "  Lançamento  "})
    assert r.status_code == 200 and r.json()["nome"] == "Lançamento"
    pid = r.json()["id"]
    assert logado.post("/api/wa/pastas", json={"nome": "Lançamento"}).status_code == 409
    assert logado.post("/api/wa/pastas", json={"nome": " "}).status_code == 400
    assert logado.patch(f"/api/wa/pastas/{pid}", json={"nome": "Black"}).json()["nome"] == "Black"
    assert logado.patch("/api/wa/pastas/99999", json={"nome": "x"}).status_code == 404
    assert [p["nome"] for p in logado.get("/api/wa/pastas").json()] == ["Black"]
    assert logado.delete(f"/api/wa/pastas/{pid}").status_code == 200
    assert logado.get("/api/wa/pastas").json() == []


def test_pasta_sobrevive_ao_sync_e_apagar_solta_os_templates(conta_wa, meta_wa, logado):
    db.salvar_templates(conta_wa["id"], [_tpl("promo"), _tpl("aviso")])
    pid = logado.post("/api/wa/pastas", json={"nome": "Black"}).json()["id"]
    r = logado.put("/api/wa/templates/pasta", json={"nome": "promo", "idioma": "pt_BR", "pasta_id": pid})
    assert r.status_code == 200 and _pasta_de(conta_wa, "promo") == "Black"
    # sync reescreve status/corpo e apaga o que sumiu, mas não mexe na pasta
    meta_wa.fila(200, {"data": [_tpl("promo", corpo="Texto novo {{1}}"), _tpl("aviso")]})
    assert logado.post("/api/wa/templates/sync").status_code == 200
    assert _pasta_de(conta_wa, "promo") == "Black" and _pasta_de(conta_wa, "aviso") == ""
    assert logado.get("/api/wa/pastas").json()[0]["total"] == 1
    logado.delete(f"/api/wa/pastas/{pid}")
    assert _pasta_de(conta_wa, "promo") == "" and len(db.listar_templates(conta_wa["id"])) == 2


def test_mover_valida_pasta_e_template(conta_wa, logado):
    db.salvar_templates(conta_wa["id"], [_tpl("promo")])
    pid = logado.post("/api/wa/pastas", json={"nome": "P"}).json()["id"]
    assert logado.put("/api/wa/templates/pasta", json={"nome": "promo", "idioma": "pt_BR", "pasta_id": 99999}).status_code == 404
    assert logado.put("/api/wa/templates/pasta", json={"nome": "nao_existe", "idioma": "pt_BR", "pasta_id": pid}).status_code == 404
    logado.put("/api/wa/templates/pasta", json={"nome": "promo", "idioma": "pt_BR", "pasta_id": pid})
    logado.put("/api/wa/templates/pasta", json={"nome": "promo", "idioma": "pt_BR", "pasta_id": None})
    assert _pasta_de(conta_wa, "promo") == ""


def test_amostras_da_meta_marcadas_e_escondidas(conta_wa, logado, sem_cooldown):
    db.salvar_templates(conta_wa["id"], [_tpl("promo"), _tpl("sample_flight_confirmation", idioma="en_US"),
                                         _tpl("hello_world", idioma="en_US")])
    amostra = {t["nome"]: t["amostra"] for t in logado.get("/api/wa/templates").json()}
    assert amostra == {"promo": False, "sample_flight_confirmation": True, "hello_world": True}
    html = logado.get("/templates").text
    assert 'data-amostra="1"' in html and 'exemplos da Meta' in html
    html = logado.get("/transmissoes/nova").text
    assert 'id="ver_amostras">' in html  # tem template próprio: amostras começam escondidas


def test_select_da_transmissao_so_aprovados_por_pasta(conta_wa, logado, sem_cooldown):
    db.salvar_templates(conta_wa["id"], [_tpl("promo"), _tpl("aviso"), _tpl("rascunho_x", status="REJECTED"),
                                         _tpl("sample_x", idioma="en_US")])
    pid = db.criar_pasta(conta_wa["id"], "Black")
    db.criar_pasta(conta_wa["id"], "Vazia")
    db.mover_template(conta_wa["id"], "promo", "pt_BR", pid)
    html = logado.get("/transmissoes/nova").text
    grupos = re.findall(r'<optgroup label="([^"]+)">(.*?)</optgroup>', html, re.S)
    assert [g for g, _ in grupos] == ["Black", "Sem pasta"]  # pasta sem aprovado não aparece
    assert 'value="promo|pt_BR"' in grupos[0][1]
    assert 'value="aviso|pt_BR"' in grupos[1][1] and 'value="sample_x|en_US"' in grupos[1][1]
    assert "rascunho_x" not in html


def test_pagina_sincroniza_pendente_com_cooldown(conta_wa, meta_wa, logado, sem_cooldown):
    db.salvar_templates(conta_wa["id"], [_tpl("novo", status="PENDING")])
    meta_wa.fila(200, {"data": [_tpl("novo")]})
    html = logado.get("/transmissoes/nova").text
    assert 'value="novo|pt_BR"' in html and len(meta_wa.chamadas) == 1
    # de novo em análise: dentro dos 60s não pergunta à Meta outra vez
    db.salvar_templates(conta_wa["id"], [_tpl("novo", status="PENDING")])
    logado.get("/templates")
    logado.get("/transmissoes/nova")
    assert len(meta_wa.chamadas) == 1
    db.set_ajuste(f"wa_tpl_autosync:{conta_wa['id']}", "0")  # passou o intervalo
    logado.get("/templates")
    assert len(meta_wa.chamadas) == 2


def test_sem_pendente_nao_chama_a_meta(conta_wa, meta_wa, logado, sem_cooldown):
    db.salvar_templates(conta_wa["id"], [_tpl("promo")])
    logado.get("/templates")
    assert meta_wa.chamadas == [] and api.sincronizar_se_pendente(conta_wa) is False


def test_pendente_mostra_atualizar(conta_wa, meta_wa, logado):
    db.salvar_templates(conta_wa["id"], [_tpl("novo", status="PENDING")])
    db.set_ajuste(f"wa_tpl_autosync:{conta_wa['id']}", "9e12")  # cooldown ativo
    assert 'class="atualizar"' in logado.get("/templates").text


def test_mcp_lista_com_pasta_e_filtra(conta_wa):
    db.salvar_templates(conta_wa["id"], [_tpl("promo"), _tpl("aviso")])
    pid = db.criar_pasta(conta_wa["id"], "Black")
    db.mover_template(conta_wa["id"], "promo", "pt_BR", pid)
    tudo = F.listar_templates_whatsapp()
    assert tudo["pastas"] == ["Black"] and {t["nome"]: t["pasta"] for t in tudo["templates"]} == {"promo": "Black", "aviso": ""}
    assert [t["nome"] for t in F.listar_templates_whatsapp(pasta="black")["templates"]] == ["promo"]
    assert [t["nome"] for t in F.listar_templates_whatsapp(pasta="sem pasta")["templates"]] == ["aviso"]
    with pytest.raises(F.ErroFerramenta, match="Black"):
        F.listar_templates_whatsapp(pasta="nao existe")


# ---------- transmissão: erro da Meta explicado e custo coerente ----------

def test_erro_131042_explicado_na_pagina(conta_wa, meta_wa, logado):
    _leads(conta_wa, 1, tag="e42")
    t = db.criar_transmissao(conta_wa["id"], "T", "oi", "pt_BR", "marketing", {}, {"tipo": "tag", "valor": "e42"}, "", 60)
    meta_wa.fila(400, {"error": {"code": 131042}})
    transmissao.tick(agora=4200.0)
    html = logado.get(f"/transmissoes/{t}").text
    assert "<code>131042</code>" in html and "forma de pagamento" in html and "Cobrança" in html
    assert transmissao.explicar_erro(999999)["texto"].startswith("Erro da Meta sem")


def test_custo_do_rascunho_igual_ao_do_formulario(conta_wa, logado):
    _leads(conta_wa, 1, tag="c1")
    t = db.criar_transmissao(conta_wa["id"], "T", "oi", "pt_BR", "marketing", {}, {"tipo": "tag", "valor": "c1"}, "", 60,
                             status="rascunho")
    r = transmissao.relatorio(t)
    assert r["previsto"] == 1 and r["custo_previsto_usd"] == pytest.approx(transmissao.preco("marketing"))
    # mesma conta e mesmo arredondamento do formulário (total × preço, 2 casas)
    assert f"US$ {1 * transmissao.preco('marketing'):.2f}" in logado.get(f"/transmissoes/{t}").text


def test_custo_previsto_tira_quem_falhou(conta_wa, meta_wa):
    _leads(conta_wa, 2, tag="c2")
    t = db.criar_transmissao(conta_wa["id"], "T", "oi", "pt_BR", "marketing", {}, {"tipo": "tag", "valor": "c2"}, "", 60)
    meta_wa.fila(400, {"error": {"code": 131026}})
    transmissao.tick(agora=4400.0)
    r = transmissao.relatorio(t)
    assert r["falhou"] == 1 and r["previsto"] == 1
