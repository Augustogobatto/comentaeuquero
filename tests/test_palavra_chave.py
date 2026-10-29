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
    ("Quero", "QUEROOO 🙏"), ("livro", "Livros!!"),
    ("livro", "livros"), ("livros", "livro"), ("livro", "quero os livros!"),
    ("ação", "ações"), ("ações", "ação"), ("limão", "limões"), ("irmão", "irmãos"),
    ("alemão", "alemães"), ("animal", "animais"), ("papel", "papéis"), ("papéis", "papel"),
    ("flor", "flores"), ("flores", "flor"), ("padre", "padres"), ("país", "países"),
    ("homem", "homens"), ("homens", "homem"), ("anzol", "anzóis"), ("azul", "azuis"),
    ("funil", "funis"), ("ebook", "EBOOKS"), ("link", "links"), ("rapaz", "rapazes"),
    ("eu quero", "eu queroo sim"), ("quero o ebook", "quero o ebooks"),
    ("promoção", "promocoes"),
])
def test_variacao_casa(palavra, texto):
    assert casa_palavra(palavra, texto) == VARIACAO


@pytest.mark.parametrize("palavra, texto", [
    ("ia", "dia"), ("ia", "bom dia"), ("ia", "dias"), ("passo", "passou"),
    ("livro", "livrinho"), ("livro", "livraria"), ("carro", "caro"),
    ("eu quero", "quero eu"), ("eu quero", "eu nao quero"), ("mes", "me manda"),
    ("quero", "querosene"), ("curso", "percurso"), ("quero", ""),
    ("quero", "🙏🙏"), ("livro", "livrinhos"),
])
def test_nao_casa(palavra, texto):
    assert casa_palavra(palavra, texto) == 0


# Plural irregular só vale quando uma palavra é plural GERADO da outra; nunca por
# "encurtar" qualquer palavra do texto (antes "mais" virava "mal", "pais" virava "pal").
@pytest.mark.parametrize("palavra, texto", [
    ("mais", "mal"), ("mal", "quero mais"), ("mães", "mão"), ("mão", "mães"),
    ("pais", "pal"), ("pal", "pais"), ("sois", "sol"), ("sol", "sois"),
    ("seis", "sel"), ("sel", "seis"), ("deus", "deu certo"), ("deu", "Deus abençoe"),
    ("mais", "mall"), ("mall", "quero mais"), ("cais", "cal"), ("cal", "cais"),
    ("vais", "val"), ("val", "vais"), ("mães", "mãos"), ("mãos", "mães"),
    ("antes", "ante"), ("ante", "antes"), ("simples", "simple"), ("lápis", "lapi"),
])
def test_plural_irregular_nao_inventa_singular(palavra, texto):
    assert casa_palavra(palavra, texto) == 0


# Até 3 letras só casa igual (depois de normalizar e desesticar), sem plural.
@pytest.mark.parametrize("palavra, texto", [
    ("me", "mes"), ("o", "os"), ("a", "as"), ("da", "das"), ("no", "nos"),
    ("ia", "IAs"), ("mês", "meses"), ("pão", "pães"), ("bom", "bons"), ("voz", "vozes"),
    ("quero o livro", "quero os livros"),
])
def test_palavra_curta_sem_plural(palavra, texto):
    assert casa_palavra(palavra, texto) == 0


@pytest.mark.parametrize("palavra, texto", [
    ("me", "ME!!"), ("o", "O"), ("ia", "IA 🙏"), ("pão", "pao"), ("sim", "siiim"),
])
def test_palavra_curta_casa_igual(palavra, texto):
    assert casa_palavra(palavra, texto) > 0


# Palavra-chave sem letra nem número: regra da v1.9.0 intacta (gatilho salvo assim
# não pode parar de disparar em silêncio). "" casa qualquer texto com letra/número.
@pytest.mark.parametrize("palavra, texto, casa", [
    ("", "qualquer coisa", True), ("", "oi", True), ("", "🙏🙏", False), ("", "!!", False),
    ("  ", "a  b", True), ("  ", "quero", False), (" ", "eu quero", True),
    ("🙏", "a🙏b", True), ("🙏", "quero 🙏", False), ("!!", "oi!!tudo", True),
    ("!!", "oi!!", False),
])
def test_palavra_sem_letra_mantem_regra_v190(palavra, texto, casa):
    assert (casa_palavra(palavra, texto) == EXATO) is casa


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


@pytest.mark.parametrize("palavra, texto, esperado", [
    ("mall", "que mal", 0), ("free", "fre", 0), ("class", "clas", 0),
    ("free", "freee", VARIACAO), ("class", "CLASSS", VARIACAO), ("link", "linkk", VARIACAO),
])
def test_esticar_so_acrescenta_letra(palavra, texto, esperado):
    """Só o texto é desesticado: palavra-chave com letra dobrada no fim não perde a
    letra ("mall" não casa "mal")."""
    assert casa_palavra(palavra, texto) == esperado


@pytest.mark.parametrize("palavra, texto, esperado", [
    ("quero", "QUERO_SIM", 0), ("quero", "QUERO_NAO", 0), ("sim", "QUERO_SIM", 0),
    ("quero_sim", "QUERO_SIM", EXATO), ("livros", "@maria_livros", 0),
    ("quero", "@fulano quero", EXATO),
])
def test_sublinhado_faz_parte_da_palavra(palavra, texto, esperado):
    """Como na v1.9.0 (\\w inclui _): payload de botão e @usuario_x não viram palavras
    soltas."""
    assert casa_palavra(palavra, texto) == esperado


def test_add_trigger_limpa_palavras_sem_mudar_significado():
    conta = _conta()
    f = db.create_flow(conta, name="limpa")
    db.add_trigger(f, "comment", keywords=["  Quero ", "Quero", "   ", ""])
    assert db.list_triggers(f)[0]["keywords"] == ["Quero", ""]
    assert _qual(conta, "oi") == "limpa"          # "" segue casando qualquer texto
    assert _qual(conta, "🙏") is None             # ... com letra/número, como na v1.9.0


def test_gatilho_com_palavra_vazia_segue_disparando():
    conta = _conta()
    _fluxo(conta, "vazio", [""])
    _fluxo(conta, "livro", ["livro"])
    assert _qual(conta, "livro") == "vazio"       # como na v1.9.0: primeiro na ordem
    assert _qual(conta, "qualquer coisa") == "vazio"
    assert _qual(conta, "🙏") is None


def test_texto_tokenizado_uma_vez_por_evento(monkeypatch):
    conta = _conta()
    for i in range(5):
        _fluxo(conta, f"f{i}", [f"palavra{i}", f"outra{i}"])
    _qual(conta, "aquece o cache")
    chamadas = []
    real = flowengine._tokens
    monkeypatch.setattr(flowengine, "_tokens", lambda s: chamadas.append(s) or real(s))
    assert _qual(conta, "quero a palavra4") == "f4"
    assert chamadas == ["quero a palavra4"]


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
