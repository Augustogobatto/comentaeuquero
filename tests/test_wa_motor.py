"""Motor no canal WhatsApp: tradução dos nós, janela por canal, saída fora_janela."""
import pytest

from app import db, runtime


@pytest.fixture(autouse=True)
def _sem_throttle(monkeypatch):
    monkeypatch.setattr(runtime, "THROTTLE_S", 0)
    monkeypatch.setattr(runtime, "LIMITER_WA", runtime.RateLimiter(1000))


def _fluxo(conta, nodes, edges):
    return db.create_flow(conta["id"], name="FWA", graph={"nodes": nodes, "edges": edges},
                          entry_node=nodes[0]["id"])


_n = [0]


def _lead_wa(conta, nome=""):
    _n[0] += 1
    l = db.lead_por_wa(conta["id"], f"55119555{_n[0]:05d}", nome)
    db.abrir_janela(l["id"], "wa")
    return db.get_lead(l["id"])


def test_texto_sai_pelo_wa(conta_wa, meta_wa):
    f = _fluxo(conta_wa, [{"id": "n1", "type": "text", "data": {"text": "Oi {name}", "link": "https://x.co"}}], [])
    l = _lead_wa(conta_wa, nome="Ana")
    assert runtime.start(conta_wa, db.get_flow(f), l, canal="wa") == "fim"
    body = meta_wa.chamadas[-1]["json"]
    assert body["to"] == l["wa_id"] and body["text"]["body"] == "Oi Ana\nhttps://x.co"
    assert db.conn().execute("SELECT origem FROM wa_mensagens WHERE wamid=?", (meta_wa.ultimo_wamid,)).fetchone()["origem"] == "fluxo"


def test_quick_replies_viram_lista_acima_de_3(conta_wa, meta_wa):
    opcoes = [{"title": f"o{n}", "key": f"k{n}"} for n in range(5)]
    f = _fluxo(conta_wa, [{"id": "n1", "type": "quick_replies", "data": {"text": "?", "options": opcoes}}], [])
    assert runtime.start(conta_wa, db.get_flow(f), _lead_wa(conta_wa), canal="wa") == "esperando_clique"
    assert meta_wa.chamadas[-1]["json"]["interactive"]["type"] == "list"


def test_quick_replies_ate_3_viram_botoes(conta_wa, meta_wa):
    opcoes = [{"title": f"o{n}", "key": f"k{n}"} for n in range(2)]
    f = _fluxo(conta_wa, [{"id": "n1", "type": "quick_replies", "data": {"text": "?", "options": opcoes}}], [])
    runtime.start(conta_wa, db.get_flow(f), _lead_wa(conta_wa), canal="wa")
    assert meta_wa.chamadas[-1]["json"]["interactive"]["type"] == "button"


def test_botao_de_link_unico_vira_cta_url(conta_wa, meta_wa):
    f = _fluxo(conta_wa, [{"id": "n1", "type": "buttons", "data": {"text": "Veja", "buttons": [{"title": "Abrir", "type": "url", "url": "https://x.co"}]}}], [])
    runtime.start(conta_wa, db.get_flow(f), _lead_wa(conta_wa), canal="wa")
    i = meta_wa.chamadas[-1]["json"]["interactive"]
    assert i["type"] == "cta_url" and i["action"]["parameters"] == {"display_text": "Abrir", "url": "https://x.co"}


def test_botoes_mistos_viram_resposta_com_link_no_texto(conta_wa, meta_wa):
    botoes = [{"title": "Sim", "key": "sim"}, {"title": "Site", "type": "url", "url": "https://x.co"}]
    f = _fluxo(conta_wa, [{"id": "n1", "type": "buttons", "data": {"text": "Veja", "buttons": botoes}}], [])
    runtime.start(conta_wa, db.get_flow(f), _lead_wa(conta_wa), canal="wa")
    i = meta_wa.chamadas[-1]["json"]["interactive"]
    assert i["type"] == "button" and "Site: https://x.co" in i["body"]["text"]


def test_fora_da_janela_segue_saida_de_falha(conta_wa, meta_wa):
    nodes = [{"id": "n1", "type": "text", "data": {"text": "livre"}},
             {"id": "n2", "type": "action", "data": {"actions": [{"action": "add_tag", "tag": "janela_fechada"}]}}]
    f = _fluxo(conta_wa, nodes, [{"id": "e", "source": "n1", "target": "n2", "sourceHandle": "fora_janela"}])
    l = db.lead_por_wa(conta_wa["id"], "5511955550001")          # sem janela aberta
    sid = db.open_session(conta_wa["id"], l["id"], f, node_id="n1", canal="wa")
    assert runtime._run(conta_wa, sid, "n1") == "fim"
    assert meta_wa.chamadas == [] and db.has_tag(l["id"], "janela_fechada")


def test_fora_da_janela_sem_saida_expira_como_hoje(conta_wa, meta_wa):
    f = _fluxo(conta_wa, [{"id": "n1", "type": "text", "data": {"text": "livre"}}], [])
    l = db.lead_por_wa(conta_wa["id"], "5511955550002")
    sid = db.open_session(conta_wa["id"], l["id"], f, node_id="n1", canal="wa")
    assert runtime._run(conta_wa, sid, "n1") == "fora_da_janela" and db.get_session(sid)["status"] == "expirada"


def test_131047_da_meta_conta_como_fora_da_janela(conta_wa, meta_wa):
    meta_wa.fila(400, {"error": {"code": 131047}})
    f = _fluxo(conta_wa, [{"id": "n1", "type": "text", "data": {"text": "x"}}], [])
    assert runtime.start(conta_wa, db.get_flow(f), _lead_wa(conta_wa), canal="wa") == "fora_da_janela"


def test_limitador_wa_nao_gasta_ficha_do_ig(conta_wa, meta_wa, monkeypatch):
    monkeypatch.setattr(runtime, "LIMITER", runtime.RateLimiter(10))
    antes = runtime.LIMITER.fichas
    f = _fluxo(conta_wa, [{"id": "n1", "type": "text", "data": {"text": "x"}}], [])
    runtime.start(conta_wa, db.get_flow(f), _lead_wa(conta_wa), canal="wa")
    assert runtime.LIMITER.fichas == pytest.approx(antes, abs=0.01)


def test_cooldown_wa_adia_sem_chamar(conta_wa, meta_wa):
    db.set_ajuste("wa_throttle_until", db.in_seconds_iso(120))
    f = _fluxo(conta_wa, [{"id": "n1", "type": "text", "data": {"text": "x"}}], [])
    assert runtime.start(conta_wa, db.get_flow(f), _lead_wa(conta_wa), canal="wa") == "adiado_rate_limit"
    assert meta_wa.chamadas == []
    db.set_ajuste("wa_throttle_until", "")


def test_sessao_ig_antiga_sem_janela_no_lead_usa_a_da_sessao(conta_wa):
    l = db.touch_lead(conta_wa["id"], "ig-velho")
    sess = {"canal": "ig", "window_expires_at": db.in_seconds_iso(3600)}
    assert runtime._dentro_da_janela(sess, l)


def test_teto_wa_limitado():
    assert runtime.aplicar_teto_wa(5) == 10 and runtime.aplicar_teto_wa(10**6) == 20000
    runtime.aplicar_teto_wa(runtime.WA_ENVIOS_POR_HORA)
