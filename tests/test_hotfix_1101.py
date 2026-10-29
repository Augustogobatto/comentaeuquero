"""Hotfix 1.10.1: link duplicado, palavra-chave com símbolo, '' misturado, palavra
curta desesticada, variável na saída da IA, controle C1/DEL e early return."""
import re
import uuid

import pytest

from app import db, flowengine, runtime, wa_traducao
from app.flowengine import EXATO, VARIACAO, casa_palavra

L = "https://loja.com/p"


# ---------- 1. link presente em forma comum não sai duplicado ----------

@pytest.mark.parametrize("texto", [
    f"Acesse:{L}", f"*{L}*", f"_{L}_", f"{L}—", f"{L}👈", f"{L}!", f"({L})",
    f'"{L}"', f"{L}\n", f"Acesse: {L}", f"{L}.", f"{L},", f"veja {L}!) e tal",
    f"{L}…", f"'{L}'", f"«{L}»", f"{L}\nmais", f"{L}. Fim", L,
])
def test_link_presente_formas_comuns(texto):
    assert wa_traducao.tem_link(texto, L) is True


@pytest.mark.parametrize("texto", [
    "veja https://loja.com/promo-fake", f"{L}/2", f"{L}?x=1", f"{L}.html",
    f"{L},x", f"{L}-x", f"{L}#a", f"{L}=1", f"{L}&a", f"{L}%20", f"{L}~a", f"{L}+a",
    f"https://golpe.com/?r={L}", f"veja https://golpe.com/x#{L}", f"x{L}", f"1{L}",
    f"/{L}", f".{L}", f"-{L}", f"~{L}", f"+{L}", f"%{L}", f"&{L}", f"?{L}", f"={L}",
    f"#{L}", "", "veja https://loja.com/",
])
def test_link_spoof_nao_conta(texto):
    assert wa_traducao.tem_link(texto, L) is False


def test_link_precedido_de_esquema_de_outra_url():
    assert wa_traducao.tem_link("abc://loja.com/p", "loja.com/p") is False
    assert wa_traducao.tem_link("veja: loja.com/p", "loja.com/p") is True


def test_link_conta_se_alguma_ocorrencia_e_inteira():
    assert wa_traducao.tem_link(f"{L}/2 e também {L}!", L) is True


def test_wa_nao_duplica_link_em_negrito(monkeypatch):
    from app import whatsapp
    enviados = []
    monkeypatch.setattr(whatsapp, "send_text",
                        lambda acc, to, texto: enviados.append(texto) or (True, None, {}))
    wa_traducao.enviar({}, {"wa_id": "55"}, {"type": "text", "data": {"link": L}},
                       f"Acesse:*{L}*👈", {}, None)
    assert enviados == [f"Acesse:*{L}*👈"]


# ---------- 2. palavra-chave com símbolo usa a regra da v1.9.0 ----------

@pytest.mark.parametrize("palavra, texto", [
    ("c++", "c"), ("c++", "eu sei c"), ("R$", "r"), ("R$", "quero r"),
    ("100%", "R$100"), ("100%", "100"), ("a@b", "a b"),
    ("x/y", "x y"), ("a=b", "a b"), ("a&b", "a b"), ("a*b", "a b"),
])
def test_simbolo_nao_some_na_normalizacao(palavra, texto):
    assert casa_palavra(palavra, texto) == 0


@pytest.mark.parametrize("palavra, texto", [
    ("a@b", "a@b"), ("x/y", "manda x/y"), ("a&b", "a&b"),
])
def test_simbolo_casa_como_na_v190(palavra, texto):
    assert re.search(r"\b" + re.escape(flowengine._normaliza(palavra)) + r"\b",
                     flowengine._normaliza(texto))
    assert casa_palavra(palavra, texto) == EXATO


@pytest.mark.parametrize("palavra, texto, esperado", [
    ("black-26", "BLACK 26", EXATO), ("black-26", "black-26!", EXATO),
    ("eu, quero", "eu quero", EXATO), ("quero!", "quero", EXATO),
    ("quero!", "queroo", VARIACAO), ("quero?", "QUERO", EXATO),
    ("d'água", "d agua", EXATO), ("Quero 🙏", "quero", EXATO),
])
def test_pontuacao_comum_segue_por_palavras(palavra, texto, esperado):
    assert casa_palavra(palavra, texto) == esperado


# ---------- 3. '' misturado com palavras some ----------

def test_vazio_junto_de_palavra_e_descartado():
    assert db._limpa_keywords(["quero", ""]) == ["quero"]
    assert db._limpa_keywords(["", "  ", "Quero "]) == ["Quero"]
    assert db._limpa_keywords([""]) == [""]          # sozinho: regra da v1.9.0
    assert db._limpa_keywords([]) == []


def test_mcp_usa_limpeza_do_db(monkeypatch):
    from app import mcp_ferramentas as F
    from tests.conftest import _so_esta_conta
    c = db.upsert_account(uuid.uuid4().hex, "", "conta_kw", "tok", "2099-01-01T00:00:00Z")
    _so_esta_conta(c["id"])
    chamadas = []
    real = db._limpa_keywords
    monkeypatch.setattr(db, "_limpa_keywords", lambda k: chamadas.append(k) or real(k))
    r = F.criar_fluxo(f"kw-{uuid.uuid4().hex[:6]}",
                      {"tipo": "comentario", "palavras": [" Quero ", "", 7]},
                      [{"tipo": "mensagem", "texto": "x"}])
    assert chamadas
    assert db.list_triggers(r["id"])[0]["keywords"] == ["Quero", "7"]
    F.adicionar_gatilho(r["id"], "direct", ["oi", ""])
    assert db.list_triggers(r["id"])[1]["keywords"] == ["oi"]


# ---------- 4. palavra curta não perde a letra final dobrada do texto ----------

@pytest.mark.parametrize("palavra, texto", [("mal", "mall"), ("bel", "bell"), ("jaz", "jazz")])
def test_curta_nao_casa_dobrada(palavra, texto):
    assert casa_palavra(palavra, texto) == 0


@pytest.mark.parametrize("palavra, texto", [("sim", "siiim"), ("quero", "queroo"),
                                            ("link", "linkk")])
def test_esticada_continua_casando(palavra, texto):
    assert casa_palavra(palavra, texto) > 0


# ---------- 5. variável escrita pela IA ----------

def _lead():
    acc = db.upsert_account(uuid.uuid4().hex, "", "conta_ia", "tok", "2099-01-01T00:00:00Z")
    lead = db.touch_lead(acc["id"], uuid.uuid4().hex[:10], "", "ana_s")
    return {**lead, "name": "ana silva", "username": "ana_s"}


@pytest.mark.parametrize("bruto, esperado", [
    ("Oi [primeiro_nome]!", "Oi Ana!"), ("Oi {primeiro_nome}!", "Oi Ana!"),
    ("Oi { Primeiro_Nome }!", "Oi Ana!"), ("Oi [ NOME ]", "Oi ana silva"),
    ("@{username} e [username]", "@ana_s e ana_s"),
    ("Segue {resposta_api} ok", "Segue ok"), ("Segue [resposta_api].", "Segue."),
    ("Link: {link}", "Link:"), ("Veja o item [2]", "Veja o item [2]"),
    ("ok { } e [ ] e [nota]", "ok { } e [ ] e [nota]"),
])
def test_saida_ia_variaveis(bruto, esperado):
    ctx = {"resposta_api": "SEGREDO {link}", "link": "https://x.com"}
    assert runtime._pos_ia(bruto, _lead(), ctx) == esperado


def test_saida_ia_nao_expande_variavel_do_contexto():
    out = runtime._pos_ia("A: {resposta_api} B: [link]", _lead(),
                          {"resposta_api": "SEGREDO", "link": "https://x.com"})
    assert out == "A: B:"


# ---------- 6. controle C1 e DEL ----------

def test_limpa_dado_tira_del_e_c1():
    assert runtime._limpa_dado("a\x7fb\x85c\x80d\x9fe\nf\tg\x00") == "abcde\nf\tg"


# ---------- 7. early return no match_trigger ----------

def _conta_com(gatilhos):
    conta = db.upsert_account(uuid.uuid4().hex, "", "c", "tok", "2099-01-01T00:00:00Z")["id"]
    for nome, kws in gatilhos:
        db.add_trigger(db.create_flow(conta, name=nome), "comment", keywords=kws)
    return conta


def test_match_para_no_primeiro_exato(monkeypatch):
    conta = _conta_com([("var", ["livros"]), ("ex", ["livro"]), ("ex2", ["livro"]),
                        ("depois", ["outra"])])
    chamadas = []
    real = flowengine._forca
    monkeypatch.setattr(flowengine, "_forca",
                        lambda k, t, a=None: chamadas.append(k) or real(k, t, a))
    assert flowengine.match_trigger(conta, "comment", "livro")["flow_name"] == "ex"
    assert chamadas == [["livros"], ["livro"]]


@pytest.mark.parametrize("gatilhos, texto, vencedor", [
    ([("var", ["livros"]), ("sempre", []), ("ex", ["livro"])], "livro", "sempre"),
    ([("var", ["livros"]), ("sempre", []), ("ex", ["livro"])], "livross", "var"),
    ([("sempre", []), ("ex", ["livro"])], "oi", "sempre"),
    ([("var", ["livro"]), ("ex", ["livros"])], "livros", "ex"),
    ([("var", ["livro"]), ("x", ["nada"])], "livros", "var"),
])
def test_match_early_return_mesmo_vencedor(gatilhos, texto, vencedor):
    assert flowengine.match_trigger(_conta_com(gatilhos), "comment", texto)["flow_name"] == vencedor


# ---------- 8. _limpa_dado uma vez por variável do dono ----------

def test_prompt_limpa_dado_do_dono_uma_vez(monkeypatch):
    ctx = {"catalogo": "itens"}
    runtime._marca_dono(ctx, {"catalogo": "itens"})
    chamadas = []
    real = runtime._limpa_dado
    monkeypatch.setattr(runtime, "_limpa_dado", lambda v: chamadas.append(v) or real(v))
    system, _ = runtime.montar_prompt_ia("Use {catalogo}", _lead(), ctx)
    assert '<campo nome="catalogo">itens</campo>' in system
    assert chamadas == ["itens"]
