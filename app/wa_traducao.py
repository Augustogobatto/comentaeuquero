"""Nó do fluxo -> mensagem do WhatsApp.

O editor é um só pros dois canais; o que muda é o formato que sai. O WhatsApp tem
regras próprias: até 3 botões de resposta, lista até 10, e botão de link é outro
tipo de mensagem (cta_url), que não mistura com botão de resposta. Quando o nó pede
algo que o WA não tem, a tradução escolhe o mais próximo sem perder conteúdo (link
vira linha no texto, carrossel vira uma imagem por cartão).
"""
import re

from . import db, whatsapp


def tem_link(texto: str, link: str) -> bool:
    """O link já está no texto como URL inteira? Substring não basta:
    "https://loja.com/p" está dentro de "https://loja.com/promo-fake". Vale só se
    depois dele vier fim, espaço, ou pontuação de fim de frase seguida de fim ou
    espaço ("veja https://loja.com/p." conta; ".../p.html" e ".../p/2" não), e se
    antes dele vier início, espaço ou pontuação de abertura, nunca caractere de
    URL: em "https://golpe.com/?r=https://loja.com/p" o link é outro."""
    if not link:
        return False
    padrao = (r"(?<![\w/=?&.:%#~+-])" + re.escape(link)
              + r"""(?=[.,;:!?)\]}"'»”’…]*(?:\s|$))""")
    return re.search(padrao, texto or "") is not None


def _e_link(b) -> bool:
    return b.get("type") == "url" or bool(b.get("url"))


def _com_links(texto, links) -> str:
    linhas = [f"{l['title']}: {l['url']}" if l.get("title") else l["url"] for l in links]
    return "\n".join([t for t in [(texto or "").strip()] if t] + linhas)


def _resultado(ok, body):
    """(ok, detalhe, wamid) a partir do retorno do whatsapp.py."""
    if ok:
        return True, str(body)[:120], whatsapp.wamid_de(body)
    if ok is None:
        return None, f"adiado {str(body)[:100]}", ""
    if whatsapp.codigo_erro(body) == whatsapp.ERRO_FORA_JANELA:
        return False, "fora_da_janela", ""
    return False, str(body)[:160], ""


def enviar(account, lead, node: dict, texto: str, ctx: dict, render):
    tipo = node.get("type")
    data = node.get("data") or {}
    to = lead.get("wa_id") or ""

    if tipo in ("text", "ai"):
        link = data.get("link") or ""
        if link and not tem_link(texto, link):
            texto = f"{texto}\n{link}".strip()
        ok, _, body = whatsapp.send_text(account, to, texto)
        return _resultado(ok, body)

    if tipo == "buttons":
        botoes = [{**b, "title": render(b.get("title", ""), lead, ctx)}
                  for b in data.get("buttons", [])]
        respostas = [b for b in botoes if not _e_link(b)]
        links = [b for b in botoes if _e_link(b)]
        if links and not respostas and len(links) == 1:
            ok, _, body = whatsapp.send_cta_url(account, to, texto, links[0]["title"],
                                                links[0]["url"])
        elif respostas:
            ok, _, body = whatsapp.send_buttons(account, to, _com_links(texto, links),
                                                respostas)
        else:
            ok, _, body = whatsapp.send_text(account, to, _com_links(texto, links))
        return _resultado(ok, body)

    if tipo == "quick_replies":
        opcoes = [{**o, "title": render(o.get("title", ""), lead, ctx)}
                  for o in data.get("options", [])]
        if len(opcoes) <= whatsapp.MAX_BOTOES:
            ok, _, body = whatsapp.send_buttons(account, to, texto, opcoes)
        else:
            if len(opcoes) > whatsapp.MAX_LINHAS:
                db.log_event("wa_opcoes_cortadas", account["id"], source="quick_replies",
                             payload={"node": node.get("id"), "total": len(opcoes)})
            ok, _, body = whatsapp.send_list(account, to, texto, opcoes)
        return _resultado(ok, body)

    if tipo == "media":
        if data.get("elements"):
            ultimo = (False, "carrossel vazio", "")
            for e in data["elements"][:10]:
                legenda = "\n".join(x for x in (e.get("title", ""), e.get("url", "")) if x)
                ok, _, body = whatsapp.send_media(account, to, e.get("image_url", ""), "image",
                                                  legenda)
                ultimo = _resultado(ok, body)
                if not ultimo[0]:
                    return ultimo
            return ultimo
        ok, _, body = whatsapp.send_media(account, to, data.get("url", ""),
                                          data.get("kind", "image"))
        return _resultado(ok, body)

    return False, f"tipo desconhecido: {tipo}", ""
