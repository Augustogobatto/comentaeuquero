"""Conexão do número em /config e estado do WhatsApp no painel."""
from app import db, segredos, wa_webhook, whatsapp
from tests.wa_helpers import _envelope


def test_salvar_conecta_e_busca_estado(logado, conta_wa, meta_wa, monkeypatch):
    monkeypatch.delenv("CEQ_ENCRYPTION_KEY", raising=False)
    meta_wa.fila(200, {"display_phone_number": "+55 11 4000-0000", "verified_name": "Loja", "quality_rating": "GREEN", "whatsapp_business_manager_messaging_limit": "TIER_250", "status": "CONNECTED"})
    meta_wa.fila(200, {"success": True})
    r = logado.post("/config", data={"wa_waba_id": "waba9", "wa_phone_number_id": "pn9", "wa_token": "tok-novo"}, follow_redirects=False)
    assert r.status_code == 303
    c = db.get_account(conta_wa["id"])
    assert (c["wa_phone_number_id"], c["wa_nome"], c["wa_limite"]) == ("pn9", "Loja", 250)
    assert segredos.ler(whatsapp.chave_token(c["id"])) == "tok-novo"
    assert meta_wa.chamadas[1]["url"].endswith("/waba9/subscribed_apps")
    ev = db.conn().execute("SELECT payload FROM events WHERE kind='config_alterada' ORDER BY id DESC LIMIT 1").fetchone()["payload"]
    assert "tok-novo" not in ev and "wa_token" in ev


def test_campo_em_branco_preserva_token(logado, conta_wa, meta_wa):
    logado.post("/config", data={"wa_token": ""})
    assert segredos.ler(whatsapp.chave_token(conta_wa["id"])) == "tok-wa"
    assert meta_wa.chamadas == []


def test_desconectar(logado, conta_wa, meta_wa):
    logado.post("/config", data={"wa_desconectar": "1"})
    assert not whatsapp.configurado(db.get_account(conta_wa["id"]))
    assert logado.get("/api/wa/estado").json() == {"configurado": False}


def test_estado_api(logado, conta_wa):
    db.update_wa_estado(conta_wa["id"], "+55 11 4000-0000", "Loja", "GREEN", 1000)
    e = logado.get("/api/wa/estado").json()
    assert e["configurado"] and e["nome"] == "Loja" and e["limite"] == 1000 and "tok-wa" not in str(e)


def test_teto_wa_e_limite_diario(logado, conta_wa, meta_wa):
    from app import runtime
    logado.post("/config", data={"wa_envios_hora": "500", "wa_limite_diario": "300"})
    assert runtime.LIMITER_WA.capacidade == 500 and db.get_ajuste("wa_limite_diario") == "300"
    db.set_ajuste("wa_limite_diario", ""); db.set_ajuste("wa_envios_hora", "")
    runtime.aplicar_teto_wa(runtime.WA_ENVIOS_POR_HORA)


def test_sem_conta_ig_ignora_campos_wa(client, monkeypatch):
    from app import main
    db.conn().execute("DELETE FROM accounts"); db.conn().commit()
    monkeypatch.setattr(main, "LOGIN_TENTATIVAS", {}); monkeypatch.setattr(main, "LOGIN_FALHAS_GLOBAIS", [])
    main.definir_senha("Minha senha 123")
    client.post("/login", data={"senha": "Minha senha 123"})
    r = client.post("/config", data={"wa_phone_number_id": "pnX"}, follow_redirects=False)
    assert "wa=sem_conta" in r.headers["location"]


def test_config_mostra_secao_wa(logado, conta_wa):
    html = logado.get("/config").text
    assert "WhatsApp (API oficial)" in html and "META_WA_APP_SECRET" in html


def test_config_sem_wa_nao_lista_segredo_wa(logado_sem_wa):
    assert "META_WA_APP_SECRET" not in logado_sem_wa.get("/config").text


def test_painel_sem_wa_igual_a_hoje(logado_sem_wa):
    html = logado_sem_wa.get("/painel").text
    assert "WhatsApp" not in html and "/transmissoes" not in html


def test_painel_com_wa_mostra_estado(logado, conta_wa):
    db.update_wa_estado(conta_wa["id"], "+55 11 4000-0000", "Loja", "GREEN", 1000)
    html = logado.get("/painel").text
    assert "Loja" in html and "1000" in html.replace(".", "") and "/transmissoes" in html


def test_webhook_de_qualidade_atualiza_limite(conta_wa):
    p = _envelope("pn1", {"display_phone_number": "5511400000000", "event": "UPGRADE", "current_limit": "TIER_10K"},
                  field="phone_number_quality_update")
    p["entry"][0]["id"] = "waba1"
    wa_webhook.process(p)
    assert db.get_account(conta_wa["id"])["wa_limite"] == 10000


def test_webhook_de_qualidade_formato_novo(conta_wa):
    """current_limit/old_limit saíram em fev/2026; o limite vem em
    max_daily_conversations_per_business (é do portfólio)."""
    p = _envelope("pn1", {"display_phone_number": "5511400000000", "event": "UPGRADE",
                          "max_daily_conversations_per_business": "TIER_50"},
                  field="phone_number_quality_update")
    wa_webhook.process(p)
    assert db.get_account(conta_wa["id"])["wa_limite"] == 50


def test_webhook_business_capability_update(conta_wa):
    for valor, esperado in (({"max_daily_conversations_per_business": "TIER_2K"}, 2000),
                            ({"max_daily_conversation_per_phone": 10000}, 10000)):
        p = _envelope("pn1", valor, field="business_capability_update")
        wa_webhook.process(p)
        assert db.get_account(conta_wa["id"])["wa_limite"] == esperado


def test_config_manda_assinar_todos_os_campos_do_webhook(logado, conta_wa):
    """Todo campo que o wa_webhook trata tem que estar na instrução de /config."""
    import re
    from pathlib import Path
    tratados = set(re.findall(r'campo == "(\w+)"', Path(wa_webhook.__file__).read_text()))
    assert {"messages", "user_preferences", "phone_number_quality_update"} <= tratados
    html = logado.get("/config").text
    for campo in tratados:
        assert f"<code>{campo}</code>" in html, campo
