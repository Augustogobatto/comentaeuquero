"""Nós Pedir WhatsApp e Template WhatsApp: a ponte do direct pro WhatsApp."""
import pytest

from app import db, instagram, runtime, wa_webhook
from tests.wa_helpers import _msg


@pytest.fixture(autouse=True)
def _sem_freio(monkeypatch):
    monkeypatch.setattr(runtime, "THROTTLE_S", 0)
    monkeypatch.setattr(runtime, "LIMITER", runtime.RateLimiter(1000))
    monkeypatch.setattr(runtime, "LIMITER_WA", runtime.RateLimiter(1000))
    db.set_ajuste("throttle_until", "")


@pytest.fixture
def ig_envios(monkeypatch):
    enviados = []

    def _send(account, recipient, texto):
        enviados.append(texto)
        return True, 200, {}
    monkeypatch.setattr(instagram, "send_text", _send)
    return enviados


_n = [0]


def _lead_ig(conta, name=""):
    _n[0] += 1
    l = db.touch_lead(conta["id"], f"ig-ponte-{_n[0]}", username=f"pessoa{_n[0]}")
    if name:
        db.conn().execute("UPDATE leads SET name=? WHERE id=?", (name, l["id"])); db.conn().commit()
    db.abrir_janela(l["id"], "ig")
    return db.get_lead(l["id"])


def test_pedir_whatsapp_valida_vincula_e_registra_optin(conta_wa, meta_wa, ig_envios):
    nodes = [{"id": "p", "type": "pedir_whatsapp", "data": {}}, {"id": "t", "type": "action", "data": {"actions": [{"action": "add_tag", "tag": "deu_zap"}]}}]
    f = db.create_flow(conta_wa["id"], graph={"nodes": nodes, "edges": [{"id": "e", "source": "p", "target": "t"}]}, entry_node="p")
    l = _lead_ig(conta_wa)
    assert runtime.start(conta_wa, db.get_flow(f), l) == "esperando_texto"
    assert "SAIR" in ig_envios[-1]
    assert runtime.resume_text(conta_wa, l, "meu numero é 123") == "entrada_invalida"
    assert "DDD" in ig_envios[-1]
    assert runtime.resume_text(conta_wa, l, "(11) 97777-0000") == "fim"
    l = db.get_lead(l["id"])
    assert l["wa_id"] == "5511977770000" and l["wa_optin_origem"] == "pedir_whatsapp" and db.has_tag(l["id"], "deu_zap")
    assert db.conn().execute("SELECT COUNT(*) FROM events WHERE kind='wa_numero_capturado' AND account_id=?", (conta_wa["id"],)).fetchone()[0] == 1


def test_template_abre_wa_e_resposta_retoma_mesma_sessao(conta_wa, meta_wa, ig_envios):
    nodes = [{"id": "p", "type": "pedir_whatsapp", "data": {}},
             {"id": "tpl", "type": "template_wa", "data": {"template": "oi", "idioma": "pt_BR", "variaveis": {"1": "{primeiro_nome}"}, "botoes": ["Quero"]}},
             {"id": "fim", "type": "text", "data": {"text": "boa!"}}]
    edges = [{"id": "a", "source": "p", "target": "tpl"}, {"id": "b", "source": "tpl", "target": "fim", "sourceHandle": "Quero"}]
    f = db.create_flow(conta_wa["id"], graph={"nodes": nodes, "edges": edges}, entry_node="p")
    l = _lead_ig(conta_wa, name="Carla Souza")
    runtime.start(conta_wa, db.get_flow(f), l)
    assert runtime.resume_text(conta_wa, l, "11977770001") == "esperando_template"
    tpl = meta_wa.chamadas[-1]["json"]["template"]
    assert tpl["name"] == "oi" and tpl["components"][0]["parameters"][0]["text"] == "Carla"
    sid = db.active_session_for_lead(l["id"])["id"]
    wa_webhook.process(_msg("pn1", "5511977770001", type="button", button={"payload": "Quero", "text": "Quero"}))
    assert meta_wa.chamadas[-1]["json"]["text"]["body"] == "boa!"
    assert db.get_session(sid)["canal"] == "wa" and db.get_session(sid)["status"] == "concluida"


def test_resposta_livre_ao_template_vai_pra_saida_padrao(conta_wa, meta_wa, ig_envios):
    nodes = [{"id": "tpl", "type": "template_wa", "data": {"template": "oi", "idioma": "pt_BR"}},
             {"id": "fim", "type": "text", "data": {"text": "recebi"}}]
    f = db.create_flow(conta_wa["id"], graph={"nodes": nodes, "edges": [{"id": "a", "source": "tpl", "target": "fim"}]}, entry_node="tpl")
    l = db.lead_por_wa(conta_wa["id"], "5511977770003"); db.registrar_optin(l["id"], "conversa")
    assert runtime.start(conta_wa, db.get_flow(f), l, canal="wa") == "esperando_template"
    wa_webhook.process(_msg("pn1", "5511977770003", type="text", text={"body": "tenho interesse"}))
    assert db.get_field(l["id"], "resposta_template") == "tenho interesse"
    assert meta_wa.chamadas[-1]["json"]["text"]["body"] == "recebi"


def test_template_bloqueado_por_optout_vai_pra_falhou(conta_wa, meta_wa):
    l = db.lead_por_wa(conta_wa["id"], "5511977770002"); db.registrar_optout(l["id"])
    nodes = [{"id": "tpl", "type": "template_wa", "data": {"template": "oi", "idioma": "pt_BR"}},
             {"id": "x", "type": "action", "data": {"actions": [{"action": "add_tag", "tag": "nao_foi"}]}}]
    f = db.create_flow(conta_wa["id"], graph={"nodes": nodes, "edges": [{"id": "e", "source": "tpl", "target": "x", "sourceHandle": "falhou"}]}, entry_node="tpl")
    runtime.start(conta_wa, db.get_flow(f), l, canal="wa")
    assert meta_wa.chamadas == [] and db.has_tag(l["id"], "nao_foi")


def test_template_que_falha_sem_saida_de_falha_nao_segue_o_caminho_de_resposta(conta_wa, meta_wa):
    l = db.lead_por_wa(conta_wa["id"], "5511977770004"); db.registrar_optout(l["id"])
    nodes = [{"id": "tpl", "type": "template_wa", "data": {"template": "oi"}},
             {"id": "x", "type": "action", "data": {"actions": [{"action": "add_tag", "tag": "respondeu"}]}}]
    f = db.create_flow(conta_wa["id"], graph={"nodes": nodes, "edges": [{"id": "e", "source": "tpl", "target": "x"}]}, entry_node="tpl")
    runtime.start(conta_wa, db.get_flow(f), l, canal="wa")
    assert not db.has_tag(l["id"], "respondeu")


def test_validador_conhece_nos_novos():
    from app import api
    g = {"nodes": [{"id": "t", "type": "template_wa", "data": {}}], "edges": []}
    avisos = api.validar_grafo(g)
    assert not any("tipo desconhecido" in a for a in avisos) and any("template do WhatsApp" in a for a in avisos)
