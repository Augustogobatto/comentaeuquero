"""Casamento de palavra-chave: variações, plural e prioridade do exato.

Um lugar só (flowengine.match_trigger) atende comentário, live, story, direct e
WhatsApp, então os casos valem para todos os canais.
"""
import uuid

import pytest

from app import db, flowengine
from app.flowengine import EXATO, VARIACAO, casa_palavra
from tests.wa_helpers import _msg


@pytest.mark.parametrize("texto", ["quero", "quero!!!", "QUERO", "Quero 🙏", "quêro",
                                   "eu quero muito", "Quero.", "#quero", "quero,quero"])
def test_quero_casa_exato(texto):
    assert casa_palavra("quero", texto) == EXATO


@pytest.mark.parametrize("palavra, texto", [
    ("quero", "queroo"), ("quero", "queroooo!!"), ("quero", "queeeero"), ("Quero", "QUEROO 🙏"),
    ("livro", "livros"), ("livros", "livro"), ("livro", "quero os livros!"),
    ("pão", "pães"), ("pães", "pão"), ("animal", "animais"), ("papel", "papéis"),
    ("flor", "flores"), ("padre", "padres"), ("mês", "meses"), ("voz", "vozes"),
    ("bom", "bons"), ("homem", "homens"), ("anzol", "anzóis"), ("azul", "azuis"),
    ("ia", "IAs"), ("eu quero", "eu queroo sim"), ("quero o livro", "quero os livros"),
    ("promoção", "promocoes"),
])
def test_variacao_casa(palavra, texto):
    assert casa_palavra(palavra, texto) == VARIACAO


@pytest.mark.parametrize("palavra, texto", [
    ("ia", "dia"), ("ia", "bom dia"), ("ia", "dias"), ("passo", "passou"),
    ("livro", "livrinho"), ("livro", "livraria"), ("carro", "caro"),
    ("eu quero", "quero eu"), ("eu quero", "eu nao quero"), ("mes", "me manda"),
    ("quero", "querosene"), ("curso", "percurso"), ("", "qualquer"), ("quero", ""),
    ("quero", "🙏🙏"),
])
def test_nao_casa(palavra, texto):
    assert casa_palavra(palavra, texto) == 0


def _conta():
    c = db.upsert_account(uuid.uuid4().hex, "", "conta_kw", "tok", "2099-01-01T00:00:00Z")
    return c["id"]


def _fluxo(conta, nome, keywords, tipo="comment"):
    f = db.create_flow(conta, name=nome)
    db.add_trigger(f, tipo, keywords=keywords)
    return nome


def _qual(conta, texto, tipo="comment"):
    t = flowengine.match_trigger(conta, tipo, texto)
    return t["flow_name"] if t else None


def test_exato_vence_variacao_nos_dois_sentidos():
    conta = _conta()
    _fluxo(conta, "singular", ["livro"])
    _fluxo(conta, "plural", ["livros"])
    assert _qual(conta, "livro") == "singular"
    assert _qual(conta, "LIVROS!!") == "plural"
    assert _qual(conta, "livroo") == "singular"


def test_exato_vence_mesmo_criado_depois():
    conta = _conta()
    _fluxo(conta, "plural", ["livros"])
    _fluxo(conta, "singular", ["livro"])
    assert _qual(conta, "livro") == "singular"


def test_variacao_dispara_quando_so_ela_existe():
    conta = _conta()
    _fluxo(conta, "livro", ["livro"])
    assert _qual(conta, "me manda os livros") == "livro"
    assert _qual(conta, "bom dia") is None


def test_responde_sempre_antes_continua_ganhando():
    """Regra de antes intacta: gatilho sem palavra criado primeiro pega tudo."""
    conta = _conta()
    _fluxo(conta, "sempre", [])
    _fluxo(conta, "livro", ["livro"])
    assert _qual(conta, "livro") == "sempre"
    assert _qual(conta, "livros") == "sempre"


def test_variacao_criada_antes_ganha_do_responde_sempre():
    conta = _conta()
    _fluxo(conta, "livro", ["livro"])
    _fluxo(conta, "sempre", [])
    assert _qual(conta, "livros") == "livro"
    assert _qual(conta, "oi") == "sempre"


def test_com_exato_em_algum_fluxo_vale_a_regra_antiga():
    conta = _conta()
    _fluxo(conta, "livro", ["livro"])
    _fluxo(conta, "sempre", [])
    _fluxo(conta, "plural", ["livros"])
    # existe exato: primeiro em ordem entre exatos e "responde sempre", como antes
    assert _qual(conta, "livros") == "sempre"


@pytest.mark.parametrize("tipo", ["comment", "live_comment", "story_reply", "dm",
                                  "wa_message", "wa_template_reply"])
def test_todos_os_canais_usam_a_mesma_regra(tipo):
    conta = _conta()
    _fluxo(conta, "livro", ["livro"], tipo)
    assert _qual(conta, "livros", tipo) == "livro"
    assert _qual(conta, "dia", tipo) is None


def test_whatsapp_ponta_a_ponta_com_plural(conta_wa, meta_wa, monkeypatch):
    from app import runtime, wa_webhook
    monkeypatch.setattr(runtime, "THROTTLE_S", 0)
    monkeypatch.setattr(runtime, "LIMITER_WA", runtime.RateLimiter(1000))
    f = db.create_flow(conta_wa["id"], name="EB",
                       graph={"nodes": [{"id": "n1", "type": "text", "data": {"text": "toma"}}],
                              "edges": []}, entry_node="n1")
    db.add_trigger(f, "wa_message", keywords=["ebook"])
    wa_webhook.process(_msg("pn1", "5511966669901", type="text", text={"body": "quero os EBOOKS!!"}))
    assert meta_wa.chamadas[-1]["json"]["text"]["body"] == "toma"
