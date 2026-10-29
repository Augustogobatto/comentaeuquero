"""Roteador de webhook do motor de fluxo: evento da Meta -> gatilho -> runtime.

Fica ao lado do engine.py v0.2, não no lugar dele. Qual dos dois atende é decisão
de uma variável de ambiente (CEQ_ENGINE), então voltar atrás no cutover é reiniciar
com outro valor, não restaurar backup.

O que este módulo faz que o v0.2 não fazia:
  - entende os gatilhos como linhas da tabela triggers (comentário, comentário em
    live, resposta de story, DM), cada um podendo ser restrito a posts específicos
  - trata clique de botão (messaging_postbacks) e de quick reply
  - entrega resposta em texto livre pra sessão que estava esperando

Herda do v0.2 tudo que já estava validado em produção: lock global, claim antes de
enviar, nunca responder a si mesmo nem a echo.
"""
import re

from . import db, instagram, runtime

# O mesmo lock do runtime, de propósito: webhook e worker precisam se excluir. Com um
# Lock() próprio aqui, os dois seguravam cadeados diferentes e podiam rodar `_run` na
# mesma sessão ao mesmo tempo (o lead respondia enquanto o timeout dele vencia, e as
# duas continuações saíam com o estado de uma sobrescrevendo o da outra).
PROCESS_LOCK = runtime.PROCESS_LOCK


# ---------- casamento de palavra-chave ----------
#
# Um lugar só para todos os canais (comentário, live, story, direct, WhatsApp): todos
# passam por match_trigger. Duas forças de casamento:
#   exato:    mesmas palavras depois de normalizar (caixa, acento, pontuação, emoji)
#   variação: além disso, letra final esticada ("queroo") e plural pt-BR ("livros")
# Exato sempre ganha de variação, então "livro" e "livros" em fluxos diferentes
# continuam separados.

EXATO, VARIACAO = 2, 1

# plural irregular pt-BR -> singular. Aplicado aos dois lados, então só precisa
# levar plural e singular para a mesma forma.
_PLURAIS = (("oes", "ao"), ("aes", "ao"), ("ais", "al"), ("eis", "el"), ("ois", "ol"),
            ("uis", "ul"), ("ns", "m"))


def _normaliza(s: str) -> str:
    import unicodedata
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", s or "")
                         if unicodedata.category(c) != "Mn")
    return sem_acento.lower()


def _tokens(s: str) -> list:
    """Palavras do texto: minúsculo, sem acento, pontuação e emoji viram espaço."""
    return re.sub(r"[\W_]+", " ", _normaliza(s)).split()


def _estica(t: str) -> str:
    """Desfaz letra esticada: 3+ iguais viram uma ("queeero"), e a última letra
    dobrada também ("queroo"). Dobra no meio ("carro") fica."""
    t = re.sub(r"([a-z])\1{2,}", r"\1", t)
    if len(t) >= 4 and t[-1].isalpha() and t[-1] == t[-2]:
        t = t[:-1]
    return t


def _formas(tok: str) -> set:
    """Formas de uma palavra para casar variação: ela, e o singular provável."""
    t = _estica(tok)
    f = {t}
    if t.endswith("s") and len(t) >= 4:        # livros, dias (não "as", "os", "mes")
        f.add(t[:-1])
    if t.endswith("es") and len(t) >= 5:       # flores, luzes, meses
        f.add(t[:-2])
    for suf, rep in _PLURAIS:                  # pães, animais, papéis, bons
        if t.endswith(suf) and len(t) > len(suf):
            f.add(t[:-len(suf)] + rep)
    return f


def _casa_sequencia(kw: list, alvo: list, igual) -> bool:
    n = len(kw)
    for i in range(len(alvo) - n + 1):
        if all(igual(kw[j], alvo[i + j]) for j in range(n)):
            return True
    return False


def casa_palavra(keyword: str, texto: str) -> int:
    """0 = não casa, VARIACAO, ou EXATO. Palavra inteira (ou frase inteira, na
    ordem), em qualquer posição do texto. "ia" nunca casa dentro de "dia"."""
    kw = _tokens(keyword)
    alvo = _tokens(texto)
    if not kw or not alvo:
        return 0
    if _casa_sequencia(kw, alvo, lambda a, b: a == b):
        return EXATO
    formas = {}

    def parecido(k, a):
        for x in (k, a):
            if x not in formas:
                formas[x] = _formas(x)
        if formas[k] & formas[a]:
            return True
        # palavra curta no plural só no sentido palavra-chave -> texto: "ia" casa "IAs",
        # "o" casa "os", mas "mes" não casa "me"
        return len(a) <= 3 and a.endswith("s") and a[:-1] == _estica(k)
    if _casa_sequencia(kw, alvo, parecido):
        return VARIACAO
    return 0


def _forca(keywords, texto) -> int:
    """Força do gatilho para este texto. Sem palavra-chave = "responde sempre"
    (devolve EXATO, como era: casa com qualquer texto)."""
    if not keywords:
        return EXATO
    if not texto:
        return 0
    return max((casa_palavra(k, texto) for k in keywords), default=0)


def _casa_keywords(keywords, texto) -> bool:
    """Compatibilidade: casa de qualquer forma (exata ou variação)."""
    return _forca(keywords, texto) > 0


def match_trigger(account_id, tipo, texto, media_id=None):
    """Gatilho ativo que casa. Ordem = ordem de criação, como no painel.

    Gatilho com media_ids preenchido só vale pros posts listados; vazio vale pra
    qualquer um. Isso é o "Reel específico" do ManyChat.

    Prioridade:
      1. Se alguma palavra-chave casou exata, vale o primeiro gatilho (na ordem) que
         casa exato ou que é "responde sempre". É a regra de antes, intacta.
      2. Senão, vale o primeiro (na ordem) entre os que casam por variação e os
         "responde sempre".
    Assim variação nunca rouba evento de um gatilho que casa exato.
    """
    candidatos = []
    for t in db.active_triggers(account_id, tipo):
        if t["media_ids"] and str(media_id or "") not in [str(m) for m in t["media_ids"]]:
            continue
        forca = _forca(t["keywords"], texto)
        if forca:
            candidatos.append((t, forca))
    if not candidatos:
        return None
    if any(f == EXATO and t["keywords"] for t, f in candidatos):
        return next(t for t, f in candidatos if f == EXATO)
    return candidatos[0][0]


def _lead_de(account, igsid, username="", keyword=""):
    lead = db.touch_lead(account["id"], str(igsid), keyword, username)
    if not lead["enriched"]:
        perfil = instagram.fetch_profile(account["access_token"], igsid)
        if perfil:
            db.enrich_lead(account["id"], lead["igsid"], perfil)
            lead = db.get_lead(lead["id"])
    return lead


def process_payload(payload: dict) -> None:
    with PROCESS_LOCK:
        _process(payload)


def _process(payload: dict) -> None:
    # WhatsApp chega no mesmo /webhook com outro objeto; quem não tem WA nunca
    # recebe isso (e se receber, o wa_webhook só registra e segue)
    if payload.get("object") == "whatsapp_business_account":
        from . import wa_webhook
        wa_webhook.process(payload)
        return
    for entry in payload.get("entry", []):
        account = db.get_account_by_ig_id(entry.get("id", ""))
        if not account:
            db.log_event("webhook_sem_conta", payload={"entry_id": entry.get("id")})
            continue
        meus_ids = {str(account["ig_id"]), str(account["ig_user_id"] or "")}

        for event in entry.get("messaging", []):
            _trata_messaging(account, event, meus_ids)

        for change in entry.get("changes", []):
            campo = change.get("field")
            if campo in ("comments", "live_comments"):
                _trata_comentario(account, change.get("value", {}), meus_ids,
                                  "live_comment" if campo == "live_comments" else "comment")


def _sessao_ig(lead):
    """Sessão ativa do lead, só se ela fala pelo Instagram. Sessão do WhatsApp não é
    retomada pelo direct: abriria a janela do WA no banco e responderia pelo WA a
    quem escreveu no Instagram."""
    sessao = db.active_session_for_lead(lead["id"])
    return sessao if sessao and runtime.canal_de(sessao) == "ig" else None


def _trata_messaging(account, event, meus_ids):
    remetente = str((event.get("sender") or {}).get("id", ""))
    if not remetente or remetente in meus_ids:
        return

    # leitura da mensagem: o Instagram avisa quando a pessoa abriu a DM. É a etapa
    # "leram" do funil. Guardado com o nome do fluxo pra atribuir à métrica certa,
    # que o evento de leitura não carrega sozinho.
    if event.get("read") and not event.get("message"):
        lead = _lead_de(account, remetente)
        db.log_event("fluxo_lido", account["id"], db.flow_name_do_lead(lead["id"]), "leitura",
                     True, lead.get("username") or remetente, {})
        return

    # clique em botão do button template
    postback = event.get("postback") or {}
    if postback:
        mid = postback.get("mid") or f"pb:{remetente}:{postback.get('payload')}"
        if not db.claim(mid):
            return
        lead = _lead_de(account, remetente)
        motivo = (runtime.resume_postback(account, lead, postback.get("payload", ""))
                  if _sessao_ig(lead) else "sem_sessao_esperando")
        db.log_event("fluxo_postback", account["id"], db.flow_name_do_lead(lead["id"]), "botao",
                     motivo not in ("sem_sessao_esperando", "sem_fluxo"),
                     lead.get("username") or remetente,
                     {"motivo": motivo, "payload": postback.get("payload", "")})
        return

    msg = event.get("message") or {}
    if msg.get("is_echo") or not msg.get("mid"):
        return
    if not db.claim(msg["mid"]):
        return

    # clique em quick reply chega como mensagem com payload
    quick = (msg.get("quick_reply") or {}).get("payload")
    if quick:
        lead = _lead_de(account, remetente)
        motivo = (runtime.resume_postback(account, lead, quick)
                  if _sessao_ig(lead) else "sem_sessao_esperando")
        db.log_event("fluxo_quick_reply", account["id"], db.flow_name_do_lead(lead["id"]),
                     "quick_reply", motivo not in ("sem_sessao_esperando", "sem_fluxo"),
                     lead.get("username") or remetente, {"motivo": motivo, "payload": quick})
        return

    texto = msg.get("text")
    if not texto:
        return

    lead = _lead_de(account, remetente)

    # se a pessoa estava parada num nó esperando resposta, o texto é a resposta.
    # isso vem ANTES do match de gatilho: quem está no meio de um fluxo não recomeça
    # do zero por ter escrito uma palavra-chave sem querer.
    sessao = _sessao_ig(lead)
    if sessao and sessao.get("waiting_for") == "text":
        motivo = runtime.resume_text(account, lead, texto)
        db.log_event("fluxo_resposta", account["id"], db.flow_name_do_lead(lead["id"]),
                     "texto", True, lead.get("username") or remetente, {"motivo": motivo})
        return

    origem = "story_reply" if (msg.get("reply_to") or {}).get("story") else "dm"
    gatilho = match_trigger(account["id"], origem, texto)
    if not gatilho:
        return
    _dispara(account, gatilho, lead, origem, texto)


def _trata_comentario(account, value, meus_ids, tipo):
    comment_id = value.get("id")
    autor = value.get("from") or {}
    if not comment_id or str(autor.get("id", "")) in meus_ids:
        return
    if not db.claim(comment_id):
        return

    texto = value.get("text") or ""
    media_id = (value.get("media") or {}).get("id")
    gatilho = match_trigger(account["id"], tipo, texto, media_id)
    if not gatilho:
        db.log_event("sem_keyword", account["id"], "", tipo, None,
                     autor.get("username", ""), {"text": texto[:200], "media": media_id})
        return

    lead = _lead_de(account, autor.get("id") or autor.get("username", ""),
                    autor.get("username", ""),
                    gatilho["keywords"][0] if gatilho["keywords"] else "")
    _dispara(account, gatilho, lead, tipo, texto, comment_id=comment_id)


def _dispara(account, gatilho, lead, origem, texto, comment_id=None, canal="ig"):
    flow = db.get_flow(gatilho["flow_id"])
    if not flow or not flow["active"]:
        return
    contexto = {"gatilho": origem, "texto_recebido": texto[:500]}
    motivo = runtime.start(account, flow, lead, comment_id=comment_id, context=contexto,
                           canal=canal)
    quem = lead.get("username") or (lead.get("wa_id") if canal == "wa" else "") or lead.get("igsid")
    db.log_event("fluxo_inicio", account["id"], flow["name"], origem,
                 motivo not in ("erro_envio", "fora_da_janela"),
                 quem,
                 {"motivo": motivo, "flow_id": flow["id"]})

    # resposta pública no próprio comentário, se o gatilho pedir. Em rodízio quando
    # há mais de uma: o comentário fica à vista de todo mundo, então repetir a mesma
    # frase embaixo de dez comentários é o jeito mais visível de parecer robô.
    publicas = gatilho.get("public_replies") or (
        [gatilho["public_reply"]] if gatilho.get("public_reply") else [])
    if comment_id and publicas and motivo not in ("erro_envio",):
        # a resposta pública também gasta rate limit, mas é cosmética: em aperto ela
        # é pulada, não enfileirada. A DM (o que o lead pediu) já foi ou está na fila.
        if instagram.cooldown_restante() > 0 or not runtime.LIMITER.tenta():
            db.log_event("public_reply_pulada", account["id"], flow["name"], origem,
                         None, lead.get("username", ""), {"comment_id": comment_id})
            return
        i = db.proximo_da_rotacao(f"rodizio:pub:{gatilho['id']}", len(publicas))
        texto_publico = runtime.render(publicas[i], lead, {})
        ok, status, body = instagram.send_public_reply(account, comment_id, texto_publico)
        db.log_event("public_reply", account["id"], flow["name"], origem, ok,
                     lead.get("username", ""),
                     {"status": status, "body": body, "variacao": i + 1})
