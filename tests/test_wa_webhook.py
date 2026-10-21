"""Webhook do WhatsApp: mensagens, statuses, opt-out e assinatura."""
import hashlib
import hmac
import json

from app import db, wa_webhook
from tests.wa_helpers import _msg, _status


def _assina(secret, corpo):
    return "sha256=" + hmac.new(secret.encode(), corpo, hashlib.sha256).hexdigest()


def test_mensagem_cria_lead_so_wa_com_optin_e_janela(conta_wa, meta_wa):
    wa_webhook.process(_msg("pn1", "5511900000001", type="text", text={"body": "oi"}, nome="Bia"))
    l = db.lead_por_wa(conta_wa["id"], "5511900000001")
    assert l["name"] == "Bia" and l["wa_optin_origem"] == "conversa" and db.janela_aberta(l, "wa")


def test_reentrega_da_mesma_mensagem_nao_duplica(conta_wa, meta_wa):
    p = _msg("pn1", "5511900000002", type="text", text={"body": "oi"}, mid="wamid.dup")
    wa_webhook.process(p); wa_webhook.process(p)
    r = db.conn().execute("SELECT interactions FROM leads WHERE account_id=? AND wa_id=?", (conta_wa["id"], "5511900000002")).fetchone()
    assert r["interactions"] == 1


def test_mensagem_wa_com_wa_id_sem_nove_cai_no_lead_do_ig(conta_wa, meta_wa):
    ig = db.touch_lead(conta_wa["id"], "ig-nove")
    db.vincular_whatsapp(ig["id"], "5511987650000")
    wa_webhook.process(_msg("pn1", "551187650000", type="text", text={"body": "oi"}))
    assert db.get_lead(ig["id"])["wa_id"] == "551187650000"
    assert db.conn().execute("SELECT COUNT(*) FROM leads WHERE account_id=? AND igsid LIKE 'wa:%'", (conta_wa["id"],)).fetchone()[0] == 0


def test_optout_e_volta(conta_wa, meta_wa):
    wa_webhook.process(_msg("pn1", "5511900000003", type="text", text={"body": "SAIR"}))
    l = db.lead_por_wa(conta_wa["id"], "5511900000003")
    assert l["wa_optout_em"] and meta_wa.chamadas[-1]["json"]["text"]["body"] == wa_webhook.TEXTO_OPTOUT
    wa_webhook.process(_msg("pn1", "5511900000003", type="text", text={"body": "voltar"}))
    assert db.get_lead(l["id"])["wa_optout_em"] == ""


def test_status_fora_de_ordem_nao_regride(conta_wa, meta_wa):
    l = db.lead_por_wa(conta_wa["id"], "5511900000004")
    db.registrar_wa_msg("wamid.s1", conta_wa["id"], l["id"], "fluxo", flow_name="F")
    wa_webhook.process(_status("pn1", "wamid.s1", "read"))
    wa_webhook.process(_status("pn1", "wamid.s1", "delivered"))
    wa_webhook.process(_status("pn1", "wamid.s1", "read"))
    linha = db.conn().execute("SELECT status FROM wa_mensagens WHERE wamid='wamid.s1'").fetchone()
    assert linha["status"] == "lido"
    assert db.conn().execute("SELECT COUNT(*) FROM events WHERE kind='fluxo_lido' AND rule_keyword='F'").fetchone()[0] == 1


def test_status_131050_marca_optout(conta_wa, meta_wa):
    l = db.lead_por_wa(conta_wa["id"], "5511900000005")
    db.registrar_wa_msg("wamid.s2", conta_wa["id"], l["id"], "template")
    wa_webhook.process(_status("pn1", "wamid.s2", "failed", errors=[{"code": 131050}]))
    assert db.get_lead(l["id"])["wa_optout_em"]


def test_preferencia_marketing_stop_e_resume(conta_wa, meta_wa):
    from tests.wa_helpers import _envelope
    l = db.lead_por_wa(conta_wa["id"], "5511900000007")
    pref = lambda v: _envelope("pn1", {"user_preferences": [{"wa_id": "5511900000007", "category": "marketing_messages", "value": v}]}, field="user_preferences")
    wa_webhook.process(pref("stop"))
    assert db.get_lead(l["id"])["wa_optout_em"]
    wa_webhook.process(pref("resume"))
    assert db.get_lead(l["id"])["wa_optout_em"] == ""


def test_payload_wa_sem_conta_configurada_so_loga(meta_wa):
    antes = db.conn().execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    wa_webhook.process(_msg("pn-desconhecido", "5511900000006", type="text", text={"body": "oi"}))
    assert db.conn().execute("SELECT COUNT(*) FROM events WHERE kind='webhook_sem_conta' AND payload LIKE '%pn-desconhecido%'").fetchone()[0] >= 1
    assert meta_wa.chamadas == []
    assert db.conn().execute("SELECT COUNT(*) FROM leads").fetchone()[0] == antes


def test_rota_aceita_assinatura_do_segredo_wa(client, monkeypatch):
    from app import flowengine, segredos
    monkeypatch.delenv("META_APP_SECRET", raising=False); monkeypatch.delenv("CEQ_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("META_WA_APP_SECRET", raising=False)
    monkeypatch.setattr(flowengine, "process_payload", lambda p: None)
    segredos.guardar("meta_app_secret", "ig-secret"); segredos.guardar("meta_wa_app_secret", "wa-secret")
    try:
        corpo = json.dumps({"object": "whatsapp_business_account", "entry": []}).encode()
        assert client.post("/webhook", content=corpo, headers={"X-Hub-Signature-256": _assina("wa-secret", corpo)}).status_code == 200
        assert client.post("/webhook", content=corpo, headers={"X-Hub-Signature-256": _assina("ig-secret", corpo)}).status_code == 403
        assert client.post("/webhook", content=corpo, headers={"X-Hub-Signature-256": _assina("outro", corpo)}).status_code == 403
        ig = json.dumps({"object": "instagram", "entry": []}).encode()
        assert client.post("/webhook", content=ig, headers={"X-Hub-Signature-256": _assina("wa-secret", ig)}).status_code == 403
        assert client.post("/webhook", content=ig, headers={"X-Hub-Signature-256": _assina("ig-secret", ig)}).status_code == 200
        segredos.guardar("meta_wa_app_secret", "")   # sem a do WA, a do IG vale de reserva
        assert client.post("/webhook", content=corpo, headers={"X-Hub-Signature-256": _assina("ig-secret", corpo)}).status_code == 200
    finally:
        segredos.guardar("meta_wa_app_secret", "")


def test_flowengine_despacha_objeto_wa(conta_wa, meta_wa):
    from app import flowengine
    flowengine.process_payload(_msg("pn1", "5511900000008", type="text", text={"body": "oi"}))
    assert db.lead_por_wa(conta_wa["id"], "5511900000008")["interactions"] == 2
