"""Transmissões: público com opt-in, fila com ritmo, teto diário, throttle e relatório."""
import pytest

from app import db, transmissao, wa_webhook
from tests.wa_helpers import _msg, _status

_n = [0]


def _leads(conta, n, tag=None):
    saida = []
    for _ in range(n):
        _n[0] += 1
        l = db.lead_por_wa(conta["id"], f"55119444{_n[0]:05d}", f"Pessoa {_n[0]}")
        db.registrar_optin(l["id"], "conversa")
        if tag:
            db.add_tag(l["id"], tag)
        saida.append(db.get_lead(l["id"]))
    return saida


@pytest.fixture(autouse=True)
def _limpo():
    db.set_ajuste("wa_throttle_until", "")
    yield
    db.set_ajuste("wa_throttle_until", "")
    db.set_ajuste("wa_limite_diario", "")


def test_publico_so_com_optin_sem_optout(conta_wa):
    a, b, c = _leads(conta_wa, 3, tag="vip")
    db.registrar_optout(b["id"])
    sem_optin = db.lead_por_wa(conta_wa["id"], "5511944440000"); db.add_tag(sem_optin["id"], "vip")
    ids = {l["id"] for l in db.publico(conta_wa["id"], {"tipo": "tag", "valor": "vip"})}
    assert ids == {a["id"], c["id"]}
    assert db.contar_publico(conta_wa["id"], {"tipo": "tag", "valor": "vip"}) == 2


def test_publico_por_campo(conta_wa):
    a, b = _leads(conta_wa, 2)
    db.set_field(a["id"], "cidade", "Recife"); db.set_field(b["id"], "cidade", "Natal")
    assert {l["id"] for l in db.publico(conta_wa["id"], {"tipo": "campo", "valor": "cidade", "campo_valor": "Recife"})} == {a["id"]}
    assert {l["id"] for l in db.publico(conta_wa["id"], {"tipo": "campo", "valor": "cidade"})} == {a["id"], b["id"]}


def test_ritmo_respeitado(conta_wa, meta_wa):
    _leads(conta_wa, 5, tag="r")
    t = db.criar_transmissao(conta_wa["id"], "T", "oi", "pt_BR", "marketing", {"1": "{primeiro_nome}"}, {"tipo": "tag", "valor": "r"}, "", 2)
    assert transmissao.tick(agora=1000.0) == 1
    assert transmissao.tick(agora=1010.0) == 0
    assert transmissao.tick(agora=1031.0) == 1
    assert transmissao.relatorio(t)["enviado"] == 2
    assert meta_wa.chamadas[-1]["json"]["template"]["components"][0]["parameters"][0]["text"] == "Pessoa"


def test_teto_diario_segura(conta_wa, meta_wa):
    db.set_ajuste("wa_limite_diario", str(db.templates_enviados_24h(conta_wa["id"]) + 1))
    _leads(conta_wa, 3, tag="teto")
    t = db.criar_transmissao(conta_wa["id"], "T", "oi", "pt_BR", "marketing", {}, {"tipo": "tag", "valor": "teto"}, "", 60)
    for s in range(10):
        transmissao.tick(agora=2000.0 + s * 5)
    r = transmissao.relatorio(t)
    assert r["enviado"] == 1 and r["pendente"] == 2
    assert db.conn().execute("SELECT COUNT(*) FROM events WHERE kind='wa_teto_diario' AND payload LIKE ?", (f'%"transmissao_id": {t}%',)).fetchone()[0] == 1


def test_throttle_nao_marca_falha(conta_wa, meta_wa):
    _leads(conta_wa, 2, tag="thr")
    t = db.criar_transmissao(conta_wa["id"], "T", "oi", "pt_BR", "marketing", {}, {"tipo": "tag", "valor": "thr"}, "", 60)
    meta_wa.fila(400, {"error": {"code": 130429}})
    transmissao.tick(agora=3000.0)
    r = transmissao.relatorio(t)
    assert r["falhou"] == 0 and r["pendente"] == 2


def test_optout_depois_de_agendar_pula(conta_wa, meta_wa):
    a, = _leads(conta_wa, 1, tag="tarde")
    t = db.criar_transmissao(conta_wa["id"], "T", "oi", "pt_BR", "marketing", {}, {"tipo": "tag", "valor": "tarde"}, "", 60)
    db.conn().execute("UPDATE transmissoes SET proximo_em=99999 WHERE id=?", (t,)); db.conn().commit()
    transmissao.tick(agora=0.0)                     # materializa a fila, ainda não é hora de enviar
    assert transmissao.relatorio(t)["pendente"] == 1
    db.registrar_optout(a["id"])
    transmissao.tick(agora=100000.0)
    assert transmissao.relatorio(t)["pulado"] == 1 and meta_wa.chamadas == []
    assert db.get_transmissao(t)["status"] == "concluida"


def test_agendada_no_futuro_nao_comeca(conta_wa, meta_wa):
    _leads(conta_wa, 1, tag="fut")
    t = db.criar_transmissao(conta_wa["id"], "T", "oi", "pt_BR", "marketing", {}, {"tipo": "tag", "valor": "fut"}, db.in_seconds_iso(3600), 60)
    transmissao.tick(agora=9e9)
    assert db.get_transmissao(t)["status"] == "agendada" and meta_wa.chamadas == []


def test_erro_definitivo_marca_falha_e_131050_descadastra(conta_wa, meta_wa):
    a, = _leads(conta_wa, 1, tag="f50")
    t = db.criar_transmissao(conta_wa["id"], "T", "oi", "pt_BR", "marketing", {}, {"tipo": "tag", "valor": "f50"}, "", 60)
    meta_wa.fila(400, {"error": {"code": 131050}})
    transmissao.tick(agora=4000.0)
    r = transmissao.relatorio(t)
    assert r["falhou"] == 1 and r["erros"] == {131050: 1} and db.get_lead(a["id"])["wa_optout_em"]


def test_status_e_resposta_entram_no_relatorio(conta_wa, meta_wa):
    a, = _leads(conta_wa, 1, tag="rel")
    t = db.criar_transmissao(conta_wa["id"], "T", "oi", "pt_BR", "marketing", {}, {"tipo": "tag", "valor": "rel"}, "", 60)
    transmissao.tick(agora=5000.0)
    w = meta_wa.ultimo_wamid
    wa_webhook.process(_status("pn1", w, "delivered", pricing={"category": "marketing", "billable": True}))
    wa_webhook.process(_status("pn1", w, "read"))
    wa_webhook.process(_msg("pn1", a["wa_id"], type="button", button={"payload": "Quero", "text": "Quero"}))
    r = transmissao.relatorio(t)
    assert (r["entregue"], r["lido"], r["respondido"]) == (1, 1, 1)
    assert r["custo_usd"] == pytest.approx(0.0625)


def test_lido_antes_de_entregue_conta_como_entregue(conta_wa, meta_wa):
    _leads(conta_wa, 1, tag="ord")
    t = db.criar_transmissao(conta_wa["id"], "T", "oi", "pt_BR", "marketing", {}, {"tipo": "tag", "valor": "ord"}, "", 60)
    transmissao.tick(agora=6000.0)
    wa_webhook.process(_status("pn1", meta_wa.ultimo_wamid, "read"))
    r = transmissao.relatorio(t)
    assert (r["entregue"], r["lido"]) == (1, 1)


def test_tela_exige_wa(client, logado_sem_wa):
    assert logado_sem_wa.post("/transmissoes", data={"nome": "x"}).status_code == 400


def test_tela_cria_e_mostra_relatorio(conta_wa, meta_wa, logado):
    db.salvar_templates(conta_wa["id"], [{"name": "oi", "language": "pt_BR", "category": "MARKETING", "status": "APPROVED",
                                          "components": [{"type": "BODY", "text": "Oi {{1}}"}]}])
    _leads(conta_wa, 2, tag="tela")
    assert logado.get("/api/wa/publico?tipo=tag&valor=tela").json() == {"total": 2}
    assert "oi" in logado.get("/transmissoes/nova").text
    r = logado.post("/transmissoes", data={"nome": "Black", "template": "oi|pt_BR", "var_1": "{primeiro_nome}",
                                            "publico_tipo": "tag", "publico_valor": "tela", "quando": "agora",
                                            "ritmo": "20"}, follow_redirects=False)
    assert r.status_code == 303
    tid = int(r.headers["location"].rsplit("/", 1)[1])
    t = db.get_transmissao(tid)
    assert t["categoria"] == "marketing" and t["ritmo_por_minuto"] == 20
    assert "Black" in logado.get(f"/transmissoes/{tid}").text
    assert logado.post(f"/transmissoes/{tid}/cancelar", follow_redirects=False).status_code == 303
    assert db.get_transmissao(tid)["status"] == "cancelada"
    assert "/transmissoes" in logado.get("/painel").text


def test_ritmo_alto_com_worker_de_5s(conta_wa, meta_wa):
    _leads(conta_wa, 100, tag="rit")
    t = db.criar_transmissao(conta_wa["id"], "T", "oi", "pt_BR", "marketing", {}, {"tipo": "tag", "valor": "rit"}, "", 80)
    for s in range(12):  # 1 minuto de worker a cada 5s
        transmissao.tick(agora=10000.0 + s * 5)
    assert 60 <= transmissao.relatorio(t)["enviado"] <= 80


def test_131056_adia_so_o_destinatario_e_a_fila_segue(conta_wa, meta_wa):
    a, b, c = _leads(conta_wa, 3, tag="par")
    t = db.criar_transmissao(conta_wa["id"], "T", "oi", "pt_BR", "marketing", {}, {"tipo": "tag", "valor": "par"}, "", 60)
    meta_wa.fila(400, {"error": {"code": 131056, "message": "pair rate limit"}})
    for s in range(4):   # 4 rodadas de 5s, ritmo 1/s: dá pra todo mundo
        transmissao.tick(agora=20000.0 + s * 5)
    r = transmissao.relatorio(t)
    assert r["enviado"] == 2 and r["pendente"] == 1 and r["falhou"] == 0
    envio_a = db.conn().execute("SELECT * FROM wa_envios WHERE transmissao_id=? AND lead_id=?", (t, a["id"])).fetchone()
    assert envio_a["status"] == "pendente" and envio_a["adiar_ate"] > 20000.0
    assert db.get_transmissao(t)["status"] == "enviando"   # não conclui com alguém adiado
    transmissao.tick(agora=envio_a["adiar_ate"] + 1)
    r = transmissao.relatorio(t)
    assert r["enviado"] == 3 and r["pendente"] == 0
    transmissao.tick(agora=envio_a["adiar_ate"] + 10)
    assert db.get_transmissao(t)["status"] == "concluida"


def test_131056_repetido_vira_falha(conta_wa, meta_wa):
    _leads(conta_wa, 1, tag="par2")
    t = db.criar_transmissao(conta_wa["id"], "T", "oi", "pt_BR", "marketing", {}, {"tipo": "tag", "valor": "par2"}, "", 60)
    agora = 30000.0
    for _ in range(transmissao.MAX_ADIAMENTOS + 1):
        meta_wa.fila(400, {"error": {"code": 131056}})
        transmissao.tick(agora=agora)
        agora += 100000
    r = transmissao.relatorio(t)
    assert r["falhou"] == 1 and r["erros"] == {131056: 1}
