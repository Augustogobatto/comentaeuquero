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
import functools
import re

from . import db, instagram, runtime
from .texto import sem_acento

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
#   variação: além disso, letra esticada ("queroo") e plural pt-BR ("livros")
# Exato sempre ganha de variação, então "livro" e "livros" em fluxos diferentes
# continuam separados.
#
# Palavra = sequência de letras, números e "_" (o \w da v1.9.0). "_" fica dentro da
# palavra de propósito: payload de botão "QUERO_NAO" não pode disparar "quero", nem
# "@maria_livros" disparar "livros".
#
# Plural é GERADO a partir do singular (livro -> livros, papel -> papéis), nunca
# deduzido "encurtando" qualquer palavra do texto. Duas palavras casam por plural
# quando uma está entre os plurais gerados da outra. Assim "mais" não vira "mal",
# "pais" não vira "pal" e "seis" não vira "sel".
#
# Palavra de até 3 letras (depois de normalizar e desesticar) só casa igual, sem
# plural nenhum, nos dois sentidos: "me" não casa "mes", "o" não casa "os", "ia" não
# casa "IAs", "pão" não casa "pães", "deu" não casa "deus". Palavra curta é onde o
# plural mais erra ("mal"/"mais", "sol"/"sois", "mão"/"mães"), então fica de fora
# inteira. Vale para cada palavra de uma frase: "quero o livro" não casa "quero os
# livros". Palavras invariáveis terminadas em s (_INVARIAVEIS) também só casam iguais.
#
# Terminação "ão" gera os três plurais ("ãos", "ões", "ães"): pela escrita não dá
# para saber qual é (mãos, ações, pães, alemães). Limitação conhecida: palavra de 4+
# letras em "ão" casa o plural de uma palavra em "ãe" que só difere nisso ("mamão"
# casa "mamães").

EXATO, VARIACAO = 2, 1
_CURTA = 3      # até 3 letras: só casa igual
_INVARIAVEIS = frozenset(
    "mais demais jamais deus cais vais sais depois pois dois seis tres mes lapis "
    "onibus virus bonus simples antes atras apos tenis pires oasis atlas".split())


_normaliza = sem_acento   # minúsculo, sem acento (app/texto.py, o mesmo da IA)


def _tokens(s: str) -> list:
    """Palavras do texto: minúsculo, sem acento; pontuação e emoji viram espaço."""
    return re.sub(r"\W+", " ", _normaliza(s)).split()


@functools.lru_cache(maxsize=4096)
def _tokens_kw(keyword: str) -> tuple:
    """_tokens da palavra-chave, com cache: a mesma palavra-chave é testada em todo
    evento que chega."""
    return tuple(_tokens(keyword))


@functools.lru_cache(maxsize=8192)
def _desestica(t: str) -> tuple:
    """Formas de uma palavra DO TEXTO sem letra esticada. Só o texto é desesticado:
    a palavra-chave é como o dono escreveu, então "mall" não casa "mal" nem "free"
    casa "fre" (esticar só acrescenta letra, nunca tira).
      - 3+ iguais viram uma e a última letra dobrada também: "queeeroooo", "queroo"
        -> "quero". Dobra no meio ("carro") fica, e a do fim só sai se sobrarem 4+
        letras ("mall" não vira "mal"; "siiim" vira "sim" pelas 3+ iguais).
      - 3+ iguais viram duas: "freee" -> "free", "classs" -> "class"."""
    um = re.sub(r"([a-z])\1{2,}", r"\1", t)
    # a última dobrada só cai se sobrar palavra de 4+ letras: "mall", "bell" e
    # "jazz" não viram "mal", "bel" e "jaz" (palavra curta só casa igual)
    if len(um) >= 5 and um[-1].isalpha() and um[-1] == um[-2]:
        um = um[:-1]
    dois = re.sub(r"([a-z])\1{2,}", r"\1\1", t)
    return tuple({t, um, dois})


def _gera_plurais(t: str) -> set:
    if t.endswith("ao"):                       # mão/ação/pão: ãos, ões, ães
        r = t[:-2]
        return {r + "aos", r + "oes", r + "aes"}
    if t[-1] in "aeiou":                       # livro, padre, aula
        return {t + "s"}
    if t.endswith(("al", "el", "ol", "ul")):   # animal, papel, anzol, azul
        return {t[:-1] + "is"}
    if t.endswith("il"):                       # funil -> funis, fóssil -> fósseis
        return {t[:-1] + "s", t[:-2] + "eis"}
    if t.endswith("m"):                        # homem -> homens
        return {t[:-1] + "ns"}
    if t[-1] in "rzs":                         # flor, rapaz, português
        return {t + "es"}
    if t[-1] == "x":                           # tórax: invariável
        return set()
    return {t + "s"}                           # link, ebook, post, hífen


@functools.lru_cache(maxsize=8192)
def _plurais(t: str) -> frozenset:
    """Plurais pt-BR prováveis de uma palavra já normalizada e desesticada. Vazio
    para palavra curta (até 3 letras) e invariável; nunca gera uma invariável."""
    if len(t) <= _CURTA or t in _INVARIAVEIS or not t.isalpha():
        return frozenset()
    return frozenset(p for p in _gera_plurais(t) if p not in _INVARIAVEIS)


class _Texto:
    """Texto do evento tokenizado e indexado UMA vez; cada palavra-chave de cada
    gatilho consulta o índice em vez de varrer o texto de novo."""
    __slots__ = ("bruto", "toks", "_pos", "_est", "_var", "_cache", "_norm")

    def __init__(self, texto):
        self.bruto = texto or ""
        self.toks = tuple(_tokens(self.bruto))
        pos = {}
        for i, t in enumerate(self.toks):
            pos.setdefault(t, []).append(i)
        self._pos = pos
        self._est = None
        self._cache = {}
        self._norm = None

    def normalizado(self):
        if self._norm is None:
            self._norm = _normaliza(self.bruto)
        return self._norm

    def _indexa_variacao(self):
        est, var = {}, {}
        for t, idx in self._pos.items():
            for e in _desestica(t):
                est.setdefault(e, set()).update(idx)
                for f in (e, *_plurais(e)):
                    var.setdefault(f, set()).update(idx)
        self._est, self._var = est, var

    def _onde_parecido(self, k):
        """Posições do texto onde está uma variação da palavra k."""
        if k not in self._cache:
            if self._est is None:
                self._indexa_variacao()
            s = set(self._var.get(k, ()))          # igual ou k é plural do texto
            for p in _plurais(k):                  # texto é plural de k
                s |= self._est.get(p, set())
            self._cache[k] = s
        return self._cache[k]

    def exato(self, kw):
        n, toks = len(kw), self.toks
        return any(toks[i:i + n] == kw for i in self._pos.get(kw[0], ()))

    def variacao(self, kw):
        n, total = len(kw), len(self.toks)
        resto = [self._onde_parecido(k) for k in kw[1:]]
        return any(i + n <= total and all(i + j + 1 in r for j, r in enumerate(resto))
                   for i in self._onde_parecido(kw[0]))


def _casa_legado(keyword: str, alvo: _Texto) -> int:
    """Palavra-chave sem nenhuma letra ou número ("", "  ", "🙏", "!!") ou com
    símbolo (_SIMBOLOS: "c++", "R$", "100%"): regra da
    v1.9.0 sem mudar nada, pra gatilho salvo assim seguir disparando como antes.
    "" casa qualquer texto com ao menos uma letra/número; os demais só casam
    entre duas letras/números (\\b dos dois lados)."""
    padrao = r"\b" + re.escape(_normaliza(keyword)) + r"\b"
    return EXATO if re.search(padrao, alvo.normalizado()) else 0


# Símbolo que a normalização apagaria mudando o sentido da palavra-chave: "c++"
# viraria "c", "R$" viraria "r", "100%" casaria "R$100". Palavra-chave com um deles
# casa pela regra da v1.9.0 (_casa_legado). Pontuação comum (espaço, hífen,
# apóstrofo, ".,!?;:" e emoji) segue por palavras.
_SIMBOLOS = frozenset("+$%#@&*/=\\^|~<>")


@functools.lru_cache(maxsize=4096)
def _tem_simbolo(keyword: str) -> bool:
    import unicodedata
    return any(c in _SIMBOLOS or unicodedata.category(c) in ("Sm", "Sc")
               for c in keyword)


def _casa(keyword: str, alvo: _Texto) -> int:
    keyword = keyword or ""
    kw = _tokens_kw(keyword)
    if not kw or _tem_simbolo(keyword):
        return _casa_legado(keyword, alvo)
    if not alvo.toks:
        return 0
    if alvo.exato(kw):
        return EXATO
    if alvo.variacao(kw):
        return VARIACAO
    return 0


def casa_palavra(keyword: str, texto: str) -> int:
    """0 = não casa, VARIACAO, ou EXATO. Palavra inteira (ou frase inteira, na
    ordem), em qualquer posição do texto. "ia" nunca casa dentro de "dia"."""
    if not texto:
        return 0
    return _casa(keyword, _Texto(texto))


def chave_palavra(keyword: str) -> str:
    """Forma comparável de uma palavra-chave, a mesma que o motor usa para o exato:
    "Eu Quero!" e "eu quero" dão a mesma chave."""
    return " ".join(_tokens_kw(keyword or "")) or (keyword or "")


def _forca(keywords, texto, alvo=None) -> int:
    """Força do gatilho para este texto. Sem palavra-chave = "responde sempre"
    (devolve EXATO, como era: casa com qualquer texto). `alvo` = texto já
    indexado (_Texto), pra não repetir o trabalho a cada gatilho."""
    if not keywords:
        return EXATO
    if not texto:
        return 0
    if alvo is None:
        alvo = _Texto(texto)
    melhor = 0
    for k in keywords:
        melhor = max(melhor, _casa(k, alvo))
        if melhor == EXATO:
            break
    return melhor


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
    primeiro = primeiro_exato = None
    alvo = _Texto(texto)      # tokeniza e indexa uma vez por evento
    for t in db.active_triggers(account_id, tipo):
        if t["media_ids"] and str(media_id or "") not in [str(m) for m in t["media_ids"]]:
            continue
        forca = _forca(t["keywords"], texto, alvo)
        if not forca:
            continue
        primeiro = primeiro or t
        if forca == EXATO:
            primeiro_exato = primeiro_exato or t
            if t["keywords"]:
                # a regra 1 já decidiu: o vencedor é o primeiro exato (ou "responde
                # sempre") até aqui, e nada que vier depois passa na frente dele
                return primeiro_exato
    return primeiro


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
