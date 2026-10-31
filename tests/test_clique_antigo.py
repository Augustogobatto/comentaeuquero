"""Toque duplo / clique em botão de mensagem anterior não mata a sessão (31/10/2026).

Caso real: "Me manda" (key quero) -> "Segui, libera" (key ja_sigo). A pessoa tocou 2x
no primeiro botão; o 2º "quero" chegou com a sessão já esperando o "ja_sigo", não achou
aresta, a sessão virou `concluida` e todo clique depois era sem_sessao_esperando.
"""
import uuid

import pytest

from app import db, flowengine, instagram, runtime, wa_webhook
from tests.wa_helpers import _msg


@pytest.fixture(autouse=True)
def _sem_throttle(monkeypatch):
    monkeypatch.setattr(runtime, "THROTTLE_S", 0)
    monkeypatch.setattr(runtime, "LIMITER", runtime.RateLimiter(1000))
    monkeypatch.setattr(runtime, "LIMITER_WA", runtime.RateLimiter(1000))


def _grafo(tipo_pede="buttons"):
    if tipo_pede == "buttons":
        pede = {"id": "n_pede", "type": "buttons", "data": {
            "text": "Segue e toca aqui", "buttons": [{"title": "✅ Segui, libera", "key": "ja_sigo"}]}}
    else:
        pede = {"id": "n_pede", "type": "quick_replies", "data": {
            "text": "Segue e toca aqui", "options": [{"title": "Segui", "key": "ja_sigo"}]}}
    return {"nodes": [
        {"id": "n0", "type": "buttons", "data": {"text": "Quer?", "buttons": [
            {"title": "Me manda", "key": "quero"}]}},
        pede,
        {"id": "n_fim", "type": "text", "data": {"text": "aqui o brinde"}}],
        "edges": [{"id": "a", "source": "n0", "target": "n_pede", "sourceHandle": "quero"},
                  {"id": "b", "source": "n_pede", "target": "n_fim", "sourceHandle": "ja_sigo"}]}


@pytest.fixture
def ig(monkeypatch):
    enviados = []

    def _ok(nome):
        def f(account, recipient, texto, *a, **k):
            enviados.append((nome, texto))
            return True, "", {}
        return f
    monkeypatch.setattr(instagram, "send_text", _ok("texto"))
    monkeypatch.setattr(instagram, "send_buttons", _ok("botoes"))
    monkeypatch.setattr(instagram, "send_quick_replies", _ok("quick"))
    monkeypatch.setattr(instagram, "fetch_profile", lambda *a, **k: None)
    acc = db.upsert_account(uuid.uuid4().hex, "", "conta_ig", "tok-ig", "2099-01-01T00:00:00Z")
    db.conn().execute("DELETE FROM accounts WHERE id<>?", (acc["id"],)); db.conn().commit()
    return db.get_account(acc["id"]), enviados


def _inicia(acc, grafo, igsid):
    f = db.create_flow(acc["id"], name="BRINDE", graph=grafo, entry_node="n0")
    lead = db.touch_lead(acc["id"], igsid, "", "felipe")
    db.abrir_janela(lead["id"], "ig")
    runtime.start(acc, db.get_flow(f), lead)
    return db.get_lead(lead["id"])


@pytest.mark.parametrize("tipo_pede", ["buttons", "quick_replies"])
def test_toque_duplo_no_primeiro_botao_nao_encerra_a_sessao(ig, tipo_pede):
    acc, enviados = ig
    lead = _inicia(acc, _grafo(tipo_pede), "ig-" + tipo_pede)
    assert runtime.resume_postback(acc, lead, "quero") == "esperando_clique"
    assert runtime.resume_postback(acc, lead, "quero") == "clique_antigo"
    s = db.active_session_for_lead(lead["id"])
    assert s and s["node_id"] == "n_pede" and s["waiting_for"] == "postback"
    runtime.resume_postback(acc, lead, "ja_sigo")
    assert enviados[-1] == ("texto", "aqui o brinde")


def test_clique_antigo_no_webhook_ig_nao_conta_como_falha(ig):
    acc, enviados = ig
    lead = _inicia(acc, _grafo(), "ig-webhook")

    def _pb(payload, mid):
        flowengine.process_payload({"object": "instagram", "entry": [{"id": acc["ig_id"], "messaging": [
            {"sender": {"id": lead["igsid"]}, "recipient": {"id": acc["ig_id"]},
             "postback": {"mid": mid, "payload": payload, "title": payload}}]}]})
    _pb("quero", "m1")
    _pb("quero", "m2")
    _pb("ja_sigo", "m3")
    assert enviados[-1] == ("texto", "aqui o brinde")
    linhas = db.conn().execute(
        "SELECT ok, payload FROM events WHERE kind='fluxo_postback' AND account_id=? ORDER BY id",
        (acc["id"],)).fetchall()
    oks = [r["ok"] for r in linhas]
    assert oks == [1, None, 1]
    assert "clique_antigo" in linhas[1]["payload"]


def test_botao_sem_key_continua_seguindo_a_aresta_padrao(ig):
    """Sem key o payload é o título renderizado/cortado: não dá pra afirmar que é de
    outro nó, então nada muda (segue a saída padrão, como antes)."""
    acc, enviados = ig
    g = {"nodes": [{"id": "n0", "type": "buttons", "data": {"text": "?", "buttons": [{"title": "Oi {first_name}"}]}},
                   {"id": "n1", "type": "text", "data": {"text": "seguiu"}}],
         "edges": [{"id": "a", "source": "n0", "target": "n1"}]}
    f = db.create_flow(acc["id"], name="SEMKEY", graph=g, entry_node="n0")
    lead = db.touch_lead(acc["id"], "ig-semkey", "", "x")
    db.abrir_janela(lead["id"], "ig")
    runtime.start(acc, db.get_flow(f), lead)
    runtime.resume_postback(acc, lead, "Oi Fulano")
    assert enviados[-1] == ("texto", "seguiu")


def test_clique_antigo_no_whatsapp(conta_wa, meta_wa):
    f = db.create_flow(conta_wa["id"], name="WABRINDE", graph=_grafo(), entry_node="n0")
    db.add_trigger(f, "wa_message", keywords=["brinde"])
    num = "5511977770001"
    wa_webhook.process(_msg("pn1", num, type="text", text={"body": "brinde"}))
    clique = lambda k: wa_webhook.process(_msg(
        "pn1", num, type="interactive",
        interactive={"type": "button_reply", "button_reply": {"id": k, "title": k}}))
    clique("quero")
    clique("quero")
    clique("ja_sigo")
    assert meta_wa.chamadas[-1]["json"]["text"]["body"] == "aqui o brinde"
    oks = [r["ok"] for r in db.conn().execute(
        "SELECT ok FROM events WHERE kind='fluxo_postback' AND account_id=? ORDER BY id",
        (conta_wa["id"],)).fetchall()]
    assert oks == [1, None, 1]
