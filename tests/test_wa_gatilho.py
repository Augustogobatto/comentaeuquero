"""Gatilhos do WhatsApp e retomada de sessão pelas respostas no WA."""
import pytest

from app import db, runtime, wa_webhook
from tests.wa_helpers import _msg


@pytest.fixture(autouse=True)
def _sem_throttle(monkeypatch):
    monkeypatch.setattr(runtime, "THROTTLE_S", 0)
    monkeypatch.setattr(runtime, "LIMITER_WA", runtime.RateLimiter(1000))


def test_palavra_chave_no_wa_dispara_fluxo_no_canal_wa(conta_wa, meta_wa):
    f = db.create_flow(conta_wa["id"], name="WAF", graph={"nodes": [{"id": "n1", "type": "text", "data": {"text": "chegou"}}], "edges": []}, entry_node="n1")
    db.add_trigger(f, "wa_message", keywords=["ebook"])
    wa_webhook.process(_msg("pn1", "5511966660001", type="text", text={"body": "quero o EBOOK"}))
    assert meta_wa.chamadas[-1]["json"]["text"]["body"] == "chegou"
    s = db.conn().execute("SELECT canal FROM flow_sessions WHERE flow_id=?", (f,)).fetchone()
    assert s["canal"] == "wa"
    assert db.conn().execute("SELECT COUNT(*) FROM events WHERE kind='fluxo_inicio' AND source='wa_message' AND rule_keyword='WAF' AND who='5511966660001'").fetchone()[0] == 1


def test_gatilho_de_dm_do_ig_nao_dispara_no_wa(conta_wa, meta_wa):
    f = db.create_flow(conta_wa["id"], graph={"nodes": [{"id": "n1", "type": "text", "data": {"text": "ig"}}], "edges": []})
    db.add_trigger(f, "dm", keywords=["curso"])
    wa_webhook.process(_msg("pn1", "5511966660002", type="text", text={"body": "curso"}))
    assert meta_wa.chamadas == []


def test_clique_em_botao_wa_segue_a_aresta(conta_wa, meta_wa):
    nodes = [{"id": "n1", "type": "buttons", "data": {"text": "?", "buttons": [{"title": "Sim", "key": "sim"}]}},
             {"id": "n2", "type": "text", "data": {"text": "foi sim"}}]
    f = db.create_flow(conta_wa["id"], graph={"nodes": nodes, "edges": [{"id": "e", "source": "n1", "target": "n2", "sourceHandle": "sim"}]}, entry_node="n1")
    db.add_trigger(f, "wa_message", keywords=["menu"])
    wa_webhook.process(_msg("pn1", "5511966660003", type="text", text={"body": "menu"}))
    wa_webhook.process(_msg("pn1", "5511966660003", type="interactive", interactive={"type": "button_reply", "button_reply": {"id": "sim", "title": "Sim"}}))
    assert meta_wa.chamadas[-1]["json"]["text"]["body"] == "foi sim"


def test_texto_no_wa_responde_wait_input_da_sessao_wa(conta_wa, meta_wa):
    nodes = [{"id": "n1", "type": "wait_input", "data": {"save_as": "cidade"}},
             {"id": "n2", "type": "text", "data": {"text": "anotado {cidade}"}}]
    f = db.create_flow(conta_wa["id"], graph={"nodes": nodes, "edges": [{"id": "e", "source": "n1", "target": "n2"}]}, entry_node="n1")
    db.add_trigger(f, "wa_message", keywords=["cadastro"])
    wa_webhook.process(_msg("pn1", "5511966660004", type="text", text={"body": "cadastro"}))
    wa_webhook.process(_msg("pn1", "5511966660004", type="text", text={"body": "Recife"}))
    assert meta_wa.chamadas[-1]["json"]["text"]["body"] == "anotado Recife"


def test_botao_de_template_sem_sessao_dispara_gatilho(conta_wa, meta_wa):
    f = db.create_flow(conta_wa["id"], name="TR", graph={"nodes": [{"id": "n1", "type": "text", "data": {"text": "valeu"}}], "edges": []}, entry_node="n1")
    db.add_trigger(f, "wa_template_reply", keywords=["Quero"])
    wa_webhook.process(_msg("pn1", "5511966660005", type="button", button={"payload": "Quero", "text": "Quero"}))
    assert meta_wa.chamadas[-1]["json"]["text"]["body"] == "valeu"


def test_api_aceita_gatilhos_wa(logado, conta_wa):
    f = db.create_flow(conta_wa["id"])
    assert logado.post(f"/api/flows/{f}/triggers", json={"type": "wa_message", "keywords": ["oi"]}).status_code == 200
    assert logado.post(f"/api/flows/{f}/triggers", json={"type": "wa_template_reply", "keywords": ["Quero"]}).status_code == 200
    assert logado.post(f"/api/flows/{f}/triggers", json={"type": "xyz"}).status_code == 400


def test_optout_encerra_sessao_wa_em_andamento(conta_wa, meta_wa):
    g = {"nodes": [{"id": "n1", "type": "text", "data": {"text": "um"}},
                   {"id": "d", "type": "delay", "data": {"seconds": 1}},
                   {"id": "n2", "type": "text", "data": {"text": "dois"}}],
         "edges": [{"source": "n1", "target": "d"}, {"source": "d", "target": "n2"}]}
    f = db.create_flow(conta_wa["id"], name="OPT", graph=g, entry_node="n1")
    db.add_trigger(f, "wa_message", keywords=["quero"])
    wa_webhook.process(_msg("pn1", "5511988880001", type="text", text={"body": "quero"}))
    wa_webhook.process(_msg("pn1", "5511988880001", type="text", text={"body": "SAIR"}))
    db.conn().execute("UPDATE jobs SET run_at='2000-01-01T00:00:00Z'"); db.conn().commit()
    antes = len(meta_wa.chamadas)
    runtime.tick()
    textos = [c["json"].get("text", {}).get("body") for c in meta_wa.chamadas[antes:] if c["json"]]
    assert "dois" not in textos


def test_envio_de_fluxo_wa_recusa_lead_com_optout(conta_wa, meta_wa):
    f = db.create_flow(conta_wa["id"], graph={"nodes": [{"id": "n1", "type": "text", "data": {"text": "x"}}], "edges": []}, entry_node="n1")
    l = db.lead_por_wa(conta_wa["id"], "5511988880002"); db.abrir_janela(l["id"], "wa"); db.registrar_optout(l["id"])
    assert runtime.start(conta_wa, db.get_flow(f), db.get_lead(l["id"]), canal="wa") == "erro_envio"
    assert meta_wa.chamadas == []
