"""Gatilho com modo "palavra exata": só dispara quando o texto é apenas a palavra.
Quando não bate, não sai nem a resposta pública nem o direct."""
import uuid

import pytest
from fastapi import HTTPException

from app import api, db, flowengine, instagram, runtime


def _conta():
    return db.upsert_account(uuid.uuid4().hex, "", "conta_ex", "tok", "2099-01-01T00:00:00Z")


def _gatilho(conta, keywords, modo="exata", nome=None, tipo="comment", **kw):
    f = db.create_flow(conta["id"], name=nome or uuid.uuid4().hex, active=1)
    return f, db.add_trigger(f, tipo, keywords=keywords, modo_palavra=modo,
                             public_replies=["te chamei no direct"], **kw)


@pytest.mark.parametrize("palavra,texto,casa", [
    ("101", "101", True),
    ("101", "  101  ", True),
    ("101", "101\n", True),
    ("101", "101!", True),
    ("101", "101 🙏", True),
    ("BLACKELA", "blackela", True),
    ("blackela", "BLACKELA ", True),
    ("promoção", "PROMOCAO", True),
    ("eu quero", "Eu  Quero!", True),
    ("101", "fazer 101", False),
    ("101", "101 por favor", False),
    ("101", "1011", False),
    ("101", "@maria 101", False),
    ("eu quero", "quero", False),
    ("livro", "livros", False),
    ("quero", "queroo", False),
    ("🙏", "🙏", True),
    ("🙏", " 🙏 ", True),
    ("🙏", "oi 🙏", False),
    ("ebook", "@ebook", False),
    ("ebook", "#ebook", False),
    ("ebook", "EBOOK?!", True),
    ("ebook", "Ébook 🔥🔥", True),
    ("ebook", "\u200bebook\u00a0", True),
    ("eu quero", "eu 🙏 quero", False),
    ("eu quero", "eu-quero", False),
    ("+1", "-1", False),
    ("+1", "1", False),
    ("+1", "+1", True),
    ("c++", "c#", False),
    ("c++", "C++ ", True),
    ("10.1", "10 1", False),
    ("10.1", "10.1", True),
    ("10.1", "10.1!", True),
    ("e-book", "E-book!", True),
    ("e-book", "e-book 🙏", True),
    ("e-book", "e book", False),
    ("quero!", "quero", True),
    ("quero!", "QUERO!!", True),
    ("sim.", "sim", True),
    ("🙏", "🙏!", True),
    ("ebook", "＠ebook", False),
    ("!!", "!!", True),
    ("!!", "oi", False),
    ("", "qualquer coisa", False),
    ("", "   ", False),
])
def test_casamento(palavra, texto, casa):
    assert bool(flowengine._forca([palavra], texto, modo="exata")) is casa


def test_uma_das_palavras_do_gatilho_basta():
    assert flowengine._forca(["101", "cento e um"], "Cento e Um", modo="exata")
    assert not flowengine._forca(["101", "cento e um"], "quero 101", modo="exata")


def test_padrao_continua_contem():
    conta = _conta()
    f = db.create_flow(conta["id"], name="padrao", active=1)
    db.add_trigger(f, "comment", keywords=["101"])
    assert db.list_triggers(f)[0]["modo_palavra"] == "contem"
    assert flowengine.match_trigger(conta["id"], "comment", "fazer 101")


def test_exata_nao_rouba_de_contem_nem_o_contrario():
    conta = _conta()
    _gatilho(conta, ["101"], "exata", nome="so_exata")
    _gatilho(conta, ["101"], "contem", nome="contem")
    assert flowengine.match_trigger(conta["id"], "comment", "101")["flow_name"] == "so_exata"
    assert flowengine.match_trigger(conta["id"], "comment", "fazer 101")["flow_name"] == "contem"


def test_vale_em_todos_os_canais():
    conta = _conta()
    for tipo in ("comment", "live_comment", "story_reply", "dm", "wa_message"):
        _gatilho(conta, ["zebra"], tipo=tipo)
        assert flowengine.match_trigger(conta["id"], tipo, "Zebra ")
        assert not flowengine.match_trigger(conta["id"], tipo, "a zebra")


def test_respeita_o_filtro_de_post():
    conta = _conta()
    _gatilho(conta, ["101"], media_ids=["m1"])
    assert flowengine.match_trigger(conta["id"], "comment", "101", "m1")
    assert not flowengine.match_trigger(conta["id"], "comment", "101", "m2")


def _comentario(conta, texto, tipo="comment"):
    flowengine._trata_comentario(
        conta, {"id": uuid.uuid4().hex, "text": texto, "from": {"id": uuid.uuid4().hex, "username": "fulana"},
                "media": {"id": "m1"}}, {conta["ig_id"]}, tipo)


def test_sem_bater_nao_envia_nada_e_batendo_envia(monkeypatch):
    publicas, inicios = [], []
    monkeypatch.setattr(instagram, "send_public_reply",
                        lambda c, cid, t: publicas.append(t) or (True, 200, "{}"))
    monkeypatch.setattr(instagram, "cooldown_restante", lambda: 0)
    monkeypatch.setattr(instagram, "fetch_profile", lambda c, i: None)
    monkeypatch.setattr(runtime, "start",
                        lambda *a, **k: inicios.append(a) or "ok")
    conta = _conta()
    _gatilho(conta, ["101"])

    _comentario(conta, "fazer 101")
    assert publicas == [] and inicios == []

    _comentario(conta, "101 ")
    assert publicas == ["te chamei no direct"] and len(inicios) == 1


def test_modo_invalido_recusa():
    conta = _conta()
    f = db.create_flow(conta["id"], name=uuid.uuid4().hex)
    with pytest.raises(ValueError):
        db.add_trigger(f, "comment", keywords=["x"], modo_palavra="regex")
    with pytest.raises(HTTPException) as e:
        api.criar_trigger(f, api.TriggerIn(type="comment", keywords=["x"], modo_palavra="regex"))
    assert e.value.status_code == 400


def test_patch_troca_modo_sem_mexer_no_resto():
    conta = _conta()
    f, tid = _gatilho(conta, ["101"], "contem")
    r = api.alternar_trigger(tid, api.TriggerPatch(modo_palavra="exata"))
    assert r["modo_palavra"] == "exata"
    t = db.list_triggers(f)[0]
    assert t["modo_palavra"] == "exata" and t["active"] == 1 and t["keywords"] == ["101"]
    assert not flowengine.match_trigger(conta["id"], "comment", "fazer 101")
    # o botão de ligar e desligar segue igual
    assert api.alternar_trigger(tid, api.TriggerPatch(active=0))["active"] == 0
    assert db.list_triggers(f)[0]["modo_palavra"] == "exata"


@pytest.mark.parametrize("patch,codigo", [
    (dict(), 400),
    (dict(modo_palavra="regex"), 400),
])
def test_patch_invalido(patch, codigo):
    conta = _conta()
    _, tid = _gatilho(conta, ["101"], "contem")
    with pytest.raises(HTTPException) as e:
        api.alternar_trigger(tid, api.TriggerPatch(**patch))
    assert e.value.status_code == codigo


def test_patch_gatilho_inexistente():
    with pytest.raises(HTTPException) as e:
        api.alternar_trigger(999999, api.TriggerPatch(modo_palavra="exata"))
    assert e.value.status_code == 404


def test_exportar_e_importar_levam_o_modo():
    conta = _conta()
    f, _ = _gatilho(conta, ["101"])
    dump = api.exportar(f)
    assert dump["triggers"][0]["modo_palavra"] == "exata"
    dump["name"] = uuid.uuid4().hex
    novo = api.importar(dump)["id"]
    assert db.list_triggers(novo)[0]["modo_palavra"] == "exata"


def test_importar_json_antigo_fica_contem():
    conta = _conta()
    f, _ = _gatilho(conta, ["101"])
    dump = api.exportar(f)
    del dump["triggers"][0]["modo_palavra"]
    dump["name"] = uuid.uuid4().hex
    assert db.list_triggers(api.importar(dump)["id"])[0]["modo_palavra"] == "contem"


@pytest.mark.parametrize("tipo,keywords", [
    ("comment", []),
    ("comment", [""]),
    ("wa_template_reply", ["Quero saber"]),
])
def test_sem_palavra_ou_botao_nunca_ficam_exata(tipo, keywords):
    conta = _conta()
    f = db.create_flow(conta["id"], name=uuid.uuid4().hex, active=1)
    tid = db.add_trigger(f, tipo, keywords=keywords, modo_palavra="exata")
    assert db.list_triggers(f)[0]["modo_palavra"] == "contem"
    with pytest.raises(HTTPException) as e:
        api.alternar_trigger(tid, api.TriggerPatch(modo_palavra="exata"))
    assert e.value.status_code == 400
    assert db.list_triggers(f)[0]["modo_palavra"] == "contem"


def test_texto_longo_de_pontuacao_nao_trava():
    import time
    texto = "a" + "!" * 4000 + "a"
    t0 = time.perf_counter()
    assert not flowengine._forca(["k%d" % i for i in range(30)], texto, modo="exata")
    assert time.perf_counter() - t0 < 0.5
