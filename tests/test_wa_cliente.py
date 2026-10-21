"""Cliente da Cloud API: formato dos payloads, número, opt-out e freio próprio."""
import pytest

from app import db, whatsapp


@pytest.mark.parametrize("entrada,saida", [
    ("(11) 98765-4321", "5511987654321"), ("11 8765-4321", "551187654321"),
    ("+55 11 98765-4321", "5511987654321"), ("551187654321", "5511987654321"),
    ("+1 415 555 0100", "14155550100"), ("123", None), ("05 98765-4321", None),
    # 0 de tronco e prefixo de operadora (0xx21 = 0 + operadora 21) de quem disca DDD
    ("011 98765-4321", "5511987654321"), ("0 11 98765-4321", "5511987654321"),
    ("(011) 8765-4321", "551187654321"), ("0xx11 98765-4321", "5511987654321"),
    ("0 21 11 98765-4321", "5511987654321"), ("021 (11) 98765-4321", "5511987654321"),
    ("0xx21 11 98765-4321", "5511987654321"), ("0 15 21 3456-7890", "552134567890"),
    ("0 59 98765-4321", None),
])
def test_normaliza_numero(entrada, saida):
    assert whatsapp.normaliza_numero(entrada) == saida


def test_variantes_br():
    assert whatsapp.variantes("551187654321") == ["551187654321", "5511987654321"]
    assert whatsapp.variantes("14155550100") == ["14155550100"]


def test_optout_so_mensagem_inteira():
    assert whatsapp.e_optout("Sair.") and whatsapp.e_optout("  PARAR ") and whatsapp.e_optout("stop")
    assert not whatsapp.e_optout("não vou parar agora") and not whatsapp.e_optout("sair daqui")


def test_limite_de_tier():
    assert whatsapp.limite_de_tier("TIER_2K") == 2000 and whatsapp.limite_de_tier("TIER_UNLIMITED") is None
    assert whatsapp.limite_de_tier("qualquer") == 250


@pytest.mark.parametrize("valor,limite", [
    ("TIER_50", 50), ("TIER_250", 250), ("TIER_1K", 1000), ("TIER_2K", 2000),
    ("TIER_10K", 10000), ("TIER_100K", 100000), ("TIER_UNLIMITED", None),
    ("tier_50", 50), ("TIER_NOT_SET", 250), ("2000", 2000), (100000, 100000),
    ({"max_daily_conversations_per_business": "TIER_50"}, 50),
    ({"current_limit": "TIER_10K"}, 10000),
])
def test_limite_de_tier_todos(valor, limite):
    assert whatsapp.limite_de_tier(valor) == limite


def test_fetch_phone_info_cai_pro_campo_antigo(conta_wa, meta_wa):
    """Se a versão da Graph recusar o campo novo (#100), pede o antigo em vez de
    deixar o painel sem estado."""
    meta_wa.fila(400, {"error": {"code": 100, "message": "Tried accessing nonexisting field (whatsapp_business_manager_messaging_limit)"}})
    meta_wa.fila(200, {"display_phone_number": "+55 11 4000-0000", "verified_name": "Loja",
                       "quality_rating": "GREEN", "messaging_limit_tier": "TIER_50", "status": "CONNECTED"})
    info = whatsapp.fetch_phone_info(conta_wa)
    assert info["limite"] == 50
    assert "messaging_limit_tier" in meta_wa.chamadas[-1]["params"]["fields"]
    assert "whatsapp_business_manager_messaging_limit" not in meta_wa.chamadas[-1]["params"]["fields"]


def test_send_buttons_formato(conta_wa, meta_wa):
    ok, _, body = whatsapp.send_buttons(conta_wa, "5511987654321", "Escolha",
        [{"title": "Quero sim, agora mesmo", "key": "sim"}, {"title": "Não", "key": "nao"}])
    c = meta_wa.chamadas[-1]
    assert ok and c["url"].endswith("/v23.0/pn1/messages")
    i = c["json"]["interactive"]
    assert c["json"]["messaging_product"] == "whatsapp" and i["type"] == "button"
    assert [b["reply"]["id"] for b in i["action"]["buttons"]] == ["sim", "nao"]
    assert len(i["action"]["buttons"][0]["reply"]["title"]) <= 20


def test_send_list_ate_10(conta_wa, meta_wa):
    whatsapp.send_list(conta_wa, "5511987654321", "Menu", [{"title": f"op {n}", "key": f"k{n}"} for n in range(12)])
    rows = meta_wa.chamadas[-1]["json"]["interactive"]["action"]["sections"][0]["rows"]
    assert len(rows) == 10 and rows[0]["id"] == "k0"


def test_send_template_parametros(conta_wa, meta_wa):
    whatsapp.send_template(conta_wa, "5511987654321", "boas_vindas", "pt_BR", ["Ana"])
    t = meta_wa.chamadas[-1]["json"]["template"]
    assert t["name"] == "boas_vindas" and t["language"] == {"code": "pt_BR"}
    assert t["components"][0]["parameters"] == [{"type": "text", "text": "Ana"}]


def test_throttle_130429_entra_em_cooldown_so_do_wa(conta_wa, meta_wa):
    from app import instagram
    db.set_ajuste("wa_throttle_until", "")
    db.set_ajuste("throttle_until", "")
    meta_wa.fila(400, {"error": {"code": 130429}})
    ok, _, _ = whatsapp.send_text(conta_wa, "5511987654321", "oi")
    assert ok is None and whatsapp.cooldown_restante() > 0 and instagram.cooldown_restante() == 0
    n = len(meta_wa.chamadas)
    assert whatsapp.send_text(conta_wa, "5511987654321", "oi")[0] is None and len(meta_wa.chamadas) == n
    db.set_ajuste("wa_throttle_until", "")


def test_131056_retenta_sem_cooldown(conta_wa, meta_wa):
    db.set_ajuste("wa_throttle_until", "")
    meta_wa.fila(400, {"error": {"code": 131056}})
    assert whatsapp.send_text(conta_wa, "5511987654321", "oi")[0] is None and whatsapp.cooldown_restante() == 0


def test_fetch_phone_info(conta_wa, meta_wa):
    meta_wa.fila(200, {"display_phone_number": "+55 11 4000-0000", "verified_name": "Loja",
                       "quality_rating": "GREEN", "whatsapp_business_manager_messaging_limit": "TIER_2K", "status": "CONNECTED"})
    assert whatsapp.fetch_phone_info(conta_wa) == {"numero": "+55 11 4000-0000", "nome": "Loja",
        "qualidade": "GREEN", "limite": 2000, "status": "CONNECTED"}


def test_sem_configuracao_nao_chama(meta_wa):
    assert not whatsapp.configurado({"id": 999, "wa_phone_number_id": ""})
    assert whatsapp.send_text({"id": 999, "wa_phone_number_id": ""}, "5511987654321", "x")[0] is False
    assert meta_wa.chamadas == []
