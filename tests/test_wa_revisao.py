"""Defeitos achados na revisão cega do canal WhatsApp, com a asserção do comportamento certo."""
import hashlib
import hmac
import json

import pytest

from app import db, flowengine, instagram, runtime, transmissao, wa_webhook
from tests.wa_helpers import _msg


@pytest.fixture(autouse=True)
def _sem_freio(monkeypatch):
    monkeypatch.setattr(runtime, "THROTTLE_S", 0)
    monkeypatch.setattr(runtime, "LIMITER", runtime.RateLimiter(1000))
    monkeypatch.setattr(runtime, "LIMITER_WA", runtime.RateLimiter(1000))
    monkeypatch.setattr(instagram, "fetch_profile", lambda *a, **k: None)
    db.set_ajuste("throttle_until", "")


def _ig_dm(conta, igsid, texto):
    return {"object": "instagram", "entry": [{"id": conta["ig_id"], "messaging": [
        {"sender": {"id": igsid}, "recipient": {"id": conta["ig_id"]},
         "message": {"mid": f"mid.{igsid}.{texto}", "text": texto}}]}]}


# 2) Fusão IG+WA: fica uma sessão ativa só e o clique no template cai na certa
def test_fusao_deixa_duas_sessoes_ativas_e_resposta_de_template_se_perde(conta_wa, meta_wa, monkeypatch):
    monkeypatch.setattr(instagram, "send_text", lambda a, r, t: (True, 200, {}))
    # fluxo IG: pedir_whatsapp -> template_wa (botão "Quero" -> tag)
    nodes = [{"id": "p", "type": "pedir_whatsapp", "data": {}},
             {"id": "tp", "type": "template_wa", "data": {"template": "oi", "idioma": "pt_BR"}},
             {"id": "tag", "type": "action", "data": {"actions": [{"action": "add_tag", "tag": "clicou"}]}}]
    edges = [{"source": "p", "target": "tp"},
             {"source": "tp", "target": "tag", "sourceHandle": "Quero"}]
    fig = db.create_flow(conta_wa["id"], name="PONTE", graph={"nodes": nodes, "edges": edges}, entry_node="p")
    lead_ig = db.touch_lead(conta_wa["id"], "1789000222", username="bia")
    db.abrir_janela(lead_ig["id"], "ig")
    assert runtime.start(conta_wa, db.get_flow(fig), db.get_lead(lead_ig["id"])) == "esperando_texto"

    # enquanto isso a pessoa fala direto no WA e entra num fluxo com botões
    nodes_wa = [{"id": "b", "type": "buttons", "data": {"text": "?", "buttons": [{"title": "Sim", "key": "sim"}]}}]
    fwa = db.create_flow(conta_wa["id"], name="WAF", graph={"nodes": nodes_wa, "edges": []}, entry_node="b")
    db.add_trigger(fwa, "wa_message", keywords=["promo"])
    wa_webhook.process(_msg("pn1", "5511912340002", type="text", text={"body": "promo"}))
    so_wa = db.lead_por_wa(conta_wa["id"], "5511912340002")
    assert db.active_session_for_lead(so_wa["id"])["waiting_for"] == "postback"

    # agora responde o número no direct -> fusão -> template enviado
    flowengine._process(_ig_dm(conta_wa, "1789000222", "11 91234-0002"))
    ativas = db.conn().execute("SELECT COUNT(*) FROM flow_sessions WHERE lead_id=? AND status='ativa'",
                               (lead_ig["id"],)).fetchone()[0]
    assert ativas == 1

    # clique no botão do template no WhatsApp
    wa_webhook.process(_msg("pn1", "5511912340002", type="button",
                            button={"payload": "Quero", "text": "Quero"}))
    assert db.has_tag(lead_ig["id"], "clicou")


# 1) DM do Instagram não retoma sessão do canal WA
def test_dm_instagram_retoma_sessao_wa_e_abre_janela_wa(conta_wa, meta_wa, monkeypatch):
    ig_enviados = []
    monkeypatch.setattr(instagram, "send_text", lambda a, r, t: (ig_enviados.append(t), (True, 200, {}))[1])
    nodes = [{"id": "w", "type": "wait_input", "data": {"text": "email?", "save_as": "email"}},
             {"id": "t", "type": "text", "data": {"text": "valeu"}}]
    f = db.create_flow(conta_wa["id"], name="X", graph={"nodes": nodes, "edges": [
        {"source": "w", "target": "t"}]}, entry_node="w")
    lead = db.touch_lead(conta_wa["id"], "1789000111", username="ana")
    db.vincular_whatsapp(lead["id"], "5511912340001")
    # sessão no canal WA esperando texto (ex.: depois do template), janela WA FECHADA
    sid = db.open_session(conta_wa["id"], lead["id"], f, node_id="w", canal="wa")
    db.update_session(sid, waiting_for="text")
    assert db.get_lead(lead["id"])["wa_janela_ate"] == ""
    antes = len(meta_wa.chamadas)

    flowengine._process(_ig_dm(conta_wa, "1789000111", "ana@x.com"))

    novos = meta_wa.chamadas[antes:]
    # DM do direct não retoma sessão do WhatsApp: nada sai pelo WA...
    assert not any((c["json"] or {}).get("type") == "text" for c in novos)
    # ...e a janela de 24h do WhatsApp continua fechada
    assert db.get_lead(lead["id"])["wa_janela_ate"] == ""
    assert db.get_session(sid)["status"] == "ativa" and db.get_session(sid)["node_id"] == "w"


# 3) Assinatura: cada produto com a sua chave
def test_segredo_do_instagram_assina_payload_do_whatsapp(client, conta_wa, meta_wa, monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "segredo-ig")
    monkeypatch.setenv("META_WA_APP_SECRET", "segredo-wa")
    corpo = json.dumps(_msg("pn1", "5511912340003", type="text", text={"body": "oi"})).encode()
    sig = "sha256=" + hmac.new(b"segredo-ig", corpo, hashlib.sha256).hexdigest()
    r = client.post("/webhook", content=corpo, headers={"X-Hub-Signature-256": sig,
                                                        "content-type": "application/json"})
    assert r.status_code in (401, 403)


# 4) Transmissão: falha de banco depois do 200 da Meta não reenvia
def test_transmissao_reenvia_se_marcar_falhar_depois_do_envio(conta_wa, meta_wa, monkeypatch):
    lead = db.lead_por_wa(conta_wa["id"], "5511912340004", "Caio")
    db.registrar_optin(lead["id"], "conversa")
    db.salvar_templates(conta_wa["id"], [{"name": "promo", "language": "pt_BR", "category": "MARKETING",
                                          "status": "APPROVED", "components": []}])
    tid = db.criar_transmissao(conta_wa["id"], "T", "promo", "pt_BR", "marketing", {}, {"tipo": "todos"}, "", 20)
    original = transmissao._marca
    travou = {"ja": False}

    def marca_que_trava(envio_id, **campos):
        if not travou["ja"] and campos.get("status") == "enviado":
            travou["ja"] = True
            import sqlite3
            raise sqlite3.OperationalError("database is locked")
        return original(envio_id, **campos)
    monkeypatch.setattr(transmissao, "_marca", marca_que_trava)
    import time
    agora = time.time()
    with pytest.raises(Exception):
        transmissao.tick(agora)
    transmissao.tick(agora + 10)
    para_ele = [c for c in meta_wa.chamadas if (c["json"] or {}).get("to") == "5511912340004"
                and (c["json"] or {}).get("type") == "template"]
    assert len(para_ele) == 1
    envio = db.conn().execute("SELECT status FROM wa_envios WHERE transmissao_id=?", (tid,)).fetchone()
    assert envio["status"] == "revisar"
    assert transmissao.relatorio(tid)["revisar"] == 1


# 5) Limite diário vazio volta pro limite do número na Meta
def test_limite_diario_nao_volta_pro_da_meta(logado, conta_wa):
    logado.post("/config", data={"wa_limite_diario": "5"}, follow_redirects=False)
    assert 'name="wa_limite_diario_no_form"' in logado.get("/config").text
    logado.post("/config", data={"wa_limite_diario": "", "wa_limite_diario_no_form": "1"},
                follow_redirects=False)
    assert db.get_ajuste("wa_limite_diario") == ""
    db.update_wa_estado(conta_wa["id"], "", "", "", 2000)
    assert transmissao.limite_diario(db.get_account(conta_wa["id"])) == 2000


def test_config_sem_o_campo_nao_apaga_limite_diario(logado, conta_wa):
    logado.post("/config", data={"wa_limite_diario": "7"}, follow_redirects=False)
    logado.post("/config", data={"wa_envios_hora": "500"}, follow_redirects=False)
    assert db.get_ajuste("wa_limite_diario") == "7"
    db.set_ajuste("wa_limite_diario", ""); db.set_ajuste("wa_envios_hora", "")
    runtime.aplicar_teto_wa(runtime.WA_ENVIOS_POR_HORA)
