"""Cliente da WhatsApp Cloud API (oficial) — Graph em graph.facebook.com.

É o único lugar do app que fala com a Graph do WhatsApp. O número mora na conta do
Instagram (colunas wa_* em accounts) e o token permanente do System User fica no
cofre (`segredos`), nunca no banco em claro nem em log.

Todas as funções de envio devolvem (ok, status, body) como o instagram.py:
ok=None não é falha, é "não enviei agora, tente depois" (freio da Meta ou par
remetente-destino saturado). O chamador reagenda em vez de descartar.
"""
import calendar
import re
import time
import unicodedata

import requests

from . import alerta, db, segredos
from .instagram import sem_segredo, truncate

GRAPH = "https://graph.facebook.com/v23.0"

# Freio próprio, separado do `throttle_until` do Instagram: a Meta mede os dois
# produtos em baldes diferentes, e o WhatsApp travado não pode calar o direct.
CODIGOS_COOLDOWN = {130429: 60, 131048: 3600, 80007: 900}   # segundos
# 131056 = mensagens demais pro MESMO destinatário em pouco tempo. É do par, não da
# conta: adia só essa mensagem, sem segurar a fila inteira.
CODIGOS_RETENTAR = {131056}
ERRO_FORA_JANELA = 131047
ERRO_OPTOUT_MARKETING = 131050

LIMITE_TEXTO = 4096
LIMITE_CORPO_INTERATIVO = 1024
LIMITE_TITULO_BOTAO = 20
LIMITE_TITULO_LINHA = 24
MAX_BOTOES = 3
MAX_LINHAS = 10

# DDDs que existem no Brasil: é o que separa "0 21 11 9…" (operadora 21 + DDD 11)
# de um número qualquer que só começa com 0.
DDDS_BR = {11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 34, 35,
           37, 38, 41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 53, 54, 55, 61, 62, 63, 64,
           65, 66, 67, 68, 69, 71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88,
           89, 91, 92, 93, 94, 95, 96, 97, 98, 99}

PALAVRAS_OPTOUT = {"sair", "parar", "stop"}
PALAVRAS_VOLTAR = {"voltar"}


def chave_token(account_id) -> str:
    return f"wa_token:{account_id}"


def token(account) -> str:
    return segredos.ler(chave_token(account["id"])) if account else ""


def configurado(account) -> bool:
    return bool(account and account.get("wa_phone_number_id") and token(account))


# ---------- número ----------

def normaliza_numero(texto) -> str | None:
    """Número digitado pela pessoa -> E.164 sem '+' (o wa_id da Meta), ou None.

    Sem DDI, 10 ou 11 dígitos é número brasileiro (DDD + número). Com 55, o celular
    antigo de 8 dígitos ganha o 9; com 13 dígitos o 9 é obrigatório. Com + ou 00 de
    outro país, aceita como veio. Discagem de longa distância brasileira também vale:
    0 de tronco ("011 9…", "0xx11 9…") e 0 + operadora de 2 dígitos ("0 21 11 9…",
    "0xx21 11 9…") saem, desde que sobre um DDD que existe.
    """
    bruto = str(texto or "").strip()
    com_ddi = bruto.startswith("+") or bruto.startswith("00")
    d = re.sub(r"\D", "", bruto)
    if bruto.startswith("00"):
        d = d[2:]
    elif d.startswith("0") and not com_ddi:
        # 0 + DDD + número (11/12 dígitos) ou 0 + operadora + DDD + número (13/14)
        tronco = {11: 1, 12: 1, 13: 3, 14: 3}.get(len(d))
        if not tronco or int(d[tronco:tronco + 2]) not in DDDS_BR:
            return None
        d = d[tronco:]
    if not com_ddi and len(d) in (10, 11):
        return ("55" + d) if int(d[:2]) >= 11 else None
    if d.startswith("55") and len(d) in (12, 13):
        if int(d[2:4]) < 11:
            return None
        if len(d) == 12:
            return d[:4] + "9" + d[4:] if d[4] in "6789" else d
        return d if d[4] == "9" else None
    if com_ddi and 8 <= len(d) <= 15:
        return d
    return None


def variantes(wa_id) -> list:
    """O número como veio e, se for celular BR, a forma com e sem o 9.

    Conta de WhatsApp antiga ainda é entregue pela Meta sem o 9; quem digitou no
    direct escreveu com. Sem as duas formas, viram dois leads da mesma pessoa.
    """
    w = str(wa_id or "")
    saida = [w]
    if w.startswith("55"):
        if len(w) == 13 and w[4] == "9":
            saida.append(w[:4] + w[5:])
        elif len(w) == 12 and w[4] in "6789":
            saida.append(w[:4] + "9" + w[4:])
    return saida


def _palavra(texto) -> str:
    sem = "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                  if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w\s]", "", sem).strip().lower()


def e_optout(texto) -> bool:
    """Só a mensagem inteira: "não vou parar agora" não descadastra ninguém."""
    return _palavra(texto) in PALAVRAS_OPTOUT


def e_optin_de_volta(texto) -> bool:
    return _palavra(texto) in PALAVRAS_VOLTAR


# Enum da Meta (webhook phone_number_quality_update e campo do número). TIER_1K não
# existe mais na doc, fica pra payload antigo. TIER_NOT_SET = número que nunca mandou
# nada: vale o limite de partida do portfólio, 250.
TIERS = {"TIER_50": 50, "TIER_250": 250, "TIER_1K": 1000, "TIER_2K": 2000,
         "TIER_10K": 10000, "TIER_100K": 100000, "TIER_UNLIMITED": None,
         "TIER_NOT_SET": 250}
LIMITE_PADRAO = 250
# Onde o limite pode vir quando chega como objeto (formato novo, por portfólio,
# e os nomes antigos do webhook).
CAMPOS_LIMITE = ("max_daily_conversations_per_business", "max_daily_conversation_per_phone",
                 "current_limit", "messaging_limit", "limit", "value")


def limite_de_tier(valor):
    """Limite de conversas iniciadas por 24h do número. None = ilimitado.

    Aceita o enum (TIER_50…TIER_UNLIMITED), número (int ou texto) e objeto com um dos
    CAMPOS_LIMITE. Valor que não dá pra ler vale LIMITE_PADRAO.
    """
    if isinstance(valor, dict):
        for campo in CAMPOS_LIMITE:
            if valor.get(campo) not in (None, ""):
                return limite_de_tier(valor[campo])
        return LIMITE_PADRAO
    if isinstance(valor, bool):
        return LIMITE_PADRAO
    if isinstance(valor, int):
        return valor
    v = str(valor or "").strip().upper()
    if v.isdigit():
        return int(v)
    return TIERS[v] if v in TIERS else LIMITE_PADRAO


# ---------- freio ----------

def cooldown_restante() -> float:
    ate = db.get_ajuste("wa_throttle_until")
    if not ate:
        return 0.0
    try:
        fim = calendar.timegm(time.strptime(ate, "%Y-%m-%dT%H:%M:%SZ"))
    except ValueError:
        return 0.0
    return max(0.0, fim - time.time())


def codigo_erro(body) -> int:
    if isinstance(body, dict):
        try:
            return int((body.get("error") or {}).get("code") or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def _entra_em_cooldown(segundos: float, origem: str) -> None:
    ja_estava = cooldown_restante() > 0
    db.set_ajuste("wa_throttle_until", db.in_seconds_iso(segundos))
    db.log_event("throttle_wa", payload={"segundos": int(segundos), "origem": origem})
    if not ja_estava:
        alerta.avisar(f"CEQ segurou os envios do WhatsApp: limite da Meta ({origem}). "
                      f"Volta em ~{max(1, int(segundos / 60))} min.")


def _corpo(r):
    try:
        if r.headers.get("content-type", "").startswith("application/json"):
            return r.json()
    except ValueError:
        pass
    return (r.text or "")[:400]


def _post(account, payload: dict, url=None, timeout=30):
    if not configurado(account):
        return False, 0, "whatsapp nao configurado"
    resta = cooldown_restante()
    if resta > 0:
        return None, 0, f"cooldown {int(resta)}s"
    url = url or f"{GRAPH}/{account['wa_phone_number_id']}/messages"
    if url.endswith("/messages"):
        payload = {"messaging_product": "whatsapp", "recipient_type": "individual", **payload}
    for tentativa in (1, 2):
        try:
            r = requests.post(url, json=payload, timeout=timeout,
                              headers={"Authorization": f"Bearer {token(account)}"})
            body = _corpo(r)
            if r.status_code == 200:
                return True, r.status_code, body
            codigo = codigo_erro(body)
            if codigo in CODIGOS_COOLDOWN or r.status_code == 429:
                _entra_em_cooldown(CODIGOS_COOLDOWN.get(codigo, 60), f"codigo {codigo or 429}")
                return None, r.status_code, body
            if codigo in CODIGOS_RETENTAR:
                return None, r.status_code, body
            if r.status_code in (500, 503) and tentativa == 1:
                time.sleep(10)
                continue
            return False, r.status_code, body
        except requests.RequestException as e:
            if tentativa == 2:
                return False, 0, sem_segredo(e)
            time.sleep(5)
    return False, 0, "unreachable"


def _get(account, caminho, params=None, url=None):
    """GET autenticado. Devolve (status, body); (0, erro) em falha de rede."""
    try:
        r = requests.get(url or f"{GRAPH}/{caminho}", params=params, timeout=20,
                         headers={"Authorization": f"Bearer {token(account)}"})
        return r.status_code, _corpo(r)
    except requests.RequestException as e:
        return 0, sem_segredo(e)


# ---------- envio ----------

def send_text(account, to, texto):
    return _post(account, {"to": str(to), "type": "text",
                           "text": {"body": truncate(texto, LIMITE_TEXTO), "preview_url": True}})


def _interativo(account, to, interativo):
    return _post(account, {"to": str(to), "type": "interactive", "interactive": interativo})


def send_buttons(account, to, texto, botoes):
    """Botões de resposta (até 3). O id volta no webhook como button_reply.id."""
    lista = [{"type": "reply", "reply": {
        "id": str(b.get("key") or b.get("title") or "")[:256],
        "title": truncate(b.get("title") or b.get("key") or "", LIMITE_TITULO_BOTAO)}}
        for b in (botoes or [])[:MAX_BOTOES]]
    if not lista:
        return send_text(account, to, texto)
    return _interativo(account, to, {
        "type": "button", "body": {"text": truncate(texto or " ", LIMITE_CORPO_INTERATIVO)},
        "action": {"buttons": lista}})


def send_list(account, to, texto, opcoes, botao="Ver opções"):
    """Lista (até 10 linhas). O id volta no webhook como list_reply.id."""
    linhas = [{"id": str(o.get("key") or o.get("title") or "")[:200],
               "title": truncate(o.get("title") or o.get("key") or "", LIMITE_TITULO_LINHA)}
              for o in (opcoes or [])[:MAX_LINHAS]]
    if not linhas:
        return send_text(account, to, texto)
    return _interativo(account, to, {
        "type": "list", "body": {"text": truncate(texto or " ", LIMITE_CORPO_INTERATIVO)},
        "action": {"button": truncate(botao, LIMITE_TITULO_BOTAO),
                   "sections": [{"rows": linhas}]}})


def send_cta_url(account, to, texto, rotulo, url):
    """Botão que abre link. O clique não volta pra gente (igual ao do Instagram)."""
    return _interativo(account, to, {
        "type": "cta_url", "body": {"text": truncate(texto or " ", LIMITE_CORPO_INTERATIVO)},
        "action": {"name": "cta_url", "parameters": {
            "display_text": truncate(rotulo or "Abrir", LIMITE_TITULO_BOTAO), "url": url}}})


def send_media(account, to, url, kind="image", legenda=""):
    if kind not in ("image", "video", "audio", "document"):
        kind = "image"
    corpo = {"link": url}
    if legenda and kind != "audio":   # áudio não aceita legenda
        corpo["caption"] = truncate(legenda, 1024)
    return _post(account, {"to": str(to), "type": kind, kind: corpo})


def send_template(account, to, nome, idioma, parametros_corpo=None):
    """Template aprovado: é o único jeito de falar com quem está fora da janela de 24h."""
    tpl = {"name": nome, "language": {"code": idioma or "pt_BR"}}
    params = [{"type": "text", "text": str(p)} for p in (parametros_corpo or [])]
    if params:
        tpl["components"] = [{"type": "body", "parameters": params}]
    return _post(account, {"to": str(to), "type": "template", "template": tpl})


def wamid_de(body) -> str:
    try:
        return str(body["messages"][0]["id"])
    except (TypeError, KeyError, IndexError):
        return ""


# ---------- número, webhook e templates ----------

CAMPOS_NUMERO = "display_phone_number,verified_name,quality_rating,status"
# Campo do limite no nó do número (Phone Number API). Desde a mudança de out/2025 o
# limite é do portfólio e a Meta lê em `whatsapp_business_manager_messaging_limit`
# (exemplo da doc: "TIER_250"); `messaging_limit_tier` está deprecado. A doc não diz
# em que versão da Graph o campo novo entrou, e campo desconhecido derruba o GET
# inteiro (#100): se isso acontecer na versão em uso, pede o antigo.
CAMPO_LIMITE_NOVO = "whatsapp_business_manager_messaging_limit"
CAMPO_LIMITE_ANTIGO = "messaging_limit_tier"


def fetch_phone_info(account) -> dict:
    """Estado do número pro painel. {} em erro (o painel mostra o que já tinha)."""
    if not configurado(account):
        return {}
    for campo in (CAMPO_LIMITE_NOVO, CAMPO_LIMITE_ANTIGO):
        status, body = _get(account, account["wa_phone_number_id"],
                            params={"fields": f"{CAMPOS_NUMERO},{campo}"})
        if status == 200 and isinstance(body, dict):
            break
        if codigo_erro(body) != 100:
            return {}
    else:
        return {}
    tier = body.get(CAMPO_LIMITE_NOVO) or body.get(CAMPO_LIMITE_ANTIGO)
    return {"numero": body.get("display_phone_number", ""),
            "nome": body.get("verified_name", ""),
            "qualidade": body.get("quality_rating", ""),
            "limite": limite_de_tier(tier),
            "status": body.get("status", "")}


def subscribe_app(account) -> tuple:
    """Assina o app nos webhooks da WABA. Idempotente na Meta."""
    if not (configurado(account) and account.get("wa_waba_id")):
        return False, "whatsapp nao configurado"
    ok, status, body = _post(account, {}, url=f"{GRAPH}/{account['wa_waba_id']}/subscribed_apps")
    return bool(ok), str(body)[:300]


def list_templates(account):
    """Lista completa, ou None se alguma página falhou: lista pela metade não pode
    virar "o resto sumiu da Meta" e apagar templates na sincronização."""
    if not (configurado(account) and account.get("wa_waba_id")):
        return []
    saida, url, params = [], None, {
        "fields": "name,status,category,language,components", "limit": 200}
    caminho = f"{account['wa_waba_id']}/message_templates"
    for _ in range(20):   # teto de páginas: conta com milhares de templates é anomalia
        status, body = _get(account, caminho, params=params, url=url)
        if status != 200 or not isinstance(body, dict):
            return None
        saida.extend(body.get("data") or [])
        url = (body.get("paging") or {}).get("next")
        params = None   # o link do próximo já traz a query
        if not url:
            break
    return saida


def create_template(account, nome, idioma, categoria, corpo, exemplos=None, botoes=None):
    """Cria o template na Meta. Quem aprova é ela; volta PENDING na hora."""
    componente = {"type": "BODY", "text": corpo}
    if exemplos:
        componente["example"] = {"body_text": [list(exemplos)]}
    componentes = [componente]
    if botoes:
        componentes.append({"type": "BUTTONS", "buttons": [
            {"type": "QUICK_REPLY", "text": b} for b in botoes]})
    ok, status, body = _post(account, {
        "name": nome, "language": idioma or "pt_BR", "category": categoria,
        "components": componentes}, url=f"{GRAPH}/{account.get('wa_waba_id')}/message_templates")
    return bool(ok), body if isinstance(body, dict) else {"error": {"message": str(body)[:300]}}
