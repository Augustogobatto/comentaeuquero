"""Cliente da Instagram API (with Instagram Login) — Graph em graph.instagram.com."""
import calendar
import json as _json
import re
import time

import requests

from . import alerta, db

GRAPH = "https://graph.instagram.com/v23.0"
OAUTH_AUTHORIZE = "https://www.instagram.com/oauth/authorize"
OAUTH_TOKEN = "https://api.instagram.com/oauth/access_token"
SCOPES = "instagram_business_basic,instagram_business_manage_messages,instagram_business_manage_comments"


_SEGREDO_NA_URL = re.compile(
    r"(?i)((?:client_secret|access_token|fb_exchange_token|code)=)[^&\s\"')>]+")


def sem_segredo(erro) -> str:
    """Texto do erro com os segredos da query apagados.

    As exceções do requests (HTTPError, ConnectionError, Timeout) trazem a URL
    completa da chamada. Nas trocas de token a URL leva client_secret e
    access_token, então o texto cru nunca pode ir pra tela nem pro log.
    """
    return _SEGREDO_NA_URL.sub(r"\1***", str(erro))


def authorize_url(app_id: str, redirect_uri: str, state: str = "") -> str:
    url = (f"{OAUTH_AUTHORIZE}?client_id={app_id}&redirect_uri={redirect_uri}"
           f"&response_type=code&scope={SCOPES}")
    return f"{url}&state={state}" if state else url


def exchange_code(app_id, app_secret, redirect_uri, code):
    """code -> token curto -> token longo (60d). Retorna dict pronto pra upsert_account."""
    r = requests.post(OAUTH_TOKEN, data={
        "client_id": app_id, "client_secret": app_secret,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri, "code": code,
    }, timeout=30)
    r.raise_for_status()
    short = r.json()

    r2 = requests.get("https://graph.instagram.com/access_token", params={
        "grant_type": "ig_exchange_token", "client_secret": app_secret,
        "access_token": short["access_token"],
    }, timeout=30)
    r2.raise_for_status()
    long_tok = r2.json()

    expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                               time.gmtime(time.time() + long_tok.get("expires_in", 5184000)))
    me = requests.get(f"{GRAPH}/me", params={
        "fields": "id,user_id,username", "access_token": long_tok["access_token"],
    }, timeout=30).json()

    return {
        "ig_id": me.get("id"),
        "ig_user_id": me.get("user_id") or short.get("user_id"),
        "username": me.get("username", ""),
        "access_token": long_tok["access_token"],
        "token_expires_at": expires_at,
        "permissions": short.get("permissions", []),
    }


def subscribe_webhooks(access_token,
                       fields="comments,live_comments,messages,messaging_postbacks"):
    """live_comments só notifica durante a transmissão; messaging_postbacks traz o
    clique em botão do fluxo. Ambos exigem que o app esteja publicado."""
    r = requests.post(f"{GRAPH}/me/subscribed_apps", params={
        "subscribed_fields": fields, "access_token": access_token}, timeout=30)
    return r.status_code == 200, r.text[:300]


def refresh_token(account: dict) -> tuple:
    """Renova token longo (precisa ter 24h+ de idade). Retorna (ok, detalhe)."""
    r = requests.get("https://graph.instagram.com/refresh_access_token", params={
        "grant_type": "ig_refresh_token", "access_token": account["access_token"]}, timeout=30)
    if r.status_code == 200:
        data = r.json()
        expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                   time.gmtime(time.time() + data.get("expires_in", 5184000)))
        db.update_token(account["id"], data["access_token"], expires_at)
        return True, expires_at
    return False, r.text[:200]


def token_days_left(account: dict) -> float:
    try:
        exp = time.mktime(time.strptime(account["token_expires_at"], "%Y-%m-%dT%H:%M:%SZ"))
        return (exp - time.time()) / 86400
    except (TypeError, ValueError):
        return -1


def fetch_own_pic(access_token) -> str:
    """Foto de perfil da própria conta conectada."""
    try:
        r = requests.get(f"{GRAPH}/me", params={
            "fields": "profile_picture_url", "access_token": access_token}, timeout=15)
        if r.status_code == 200:
            return r.json().get("profile_picture_url", "")
    except requests.RequestException:
        pass
    return ""


def download_pic(url) -> bytes:
    """Baixa a imagem da foto de perfil. b'' se não vier imagem válida."""
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
            return r.content
    except requests.RequestException:
        pass
    return b""


def fetch_profile(access_token, igsid) -> dict:
    """Perfil de quem interage (User Profile API): nome, @, foto, seguidores, segue-você.
    Retorna {} se a API não permitir (ex.: alguns comentaristas)."""
    try:
        r = requests.get(f"{GRAPH}/{igsid}", params={
            "fields": "name,username,profile_pic,follower_count,is_user_follow_business",
            "access_token": access_token}, timeout=15)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return {}


def fetch_username(access_token, igsid) -> str:
    try:
        r = requests.get(f"{GRAPH}/{igsid}", params={
            "fields": "username", "access_token": access_token}, timeout=15)
        if r.status_code == 200:
            return r.json().get("username", "")
    except requests.RequestException:
        pass
    return ""


# ---------- freio da Meta (throttle) ----------
#
# Estourar limite de API não bane a conta: a Meta responde com código de throttle
# (80002 no messaging do Instagram; 4/17/32/613 nas outras famílias) e espera que a
# gente PARE. Insistir é o que os classificadores de spam flagram como bot. Então o
# cooldown fica gravado em `ajustes` (sobrevive a restart) e, enquanto vigente,
# nenhum POST sai: quem chamar recebe ok=None e o motor reagenda pra depois.
#
# O cooldown é global da instância, não por conta, porque o produto roda uma conta
# por instalação e o limite da Meta é por conta. Se um dia virar multi-conta, muda.

CODIGOS_THROTTLE = {4, 17, 32, 613, 80002}
COOLDOWN_PADRAO_S = 900   # quando a Meta não diz quanto esperar


def cooldown_restante() -> float:
    """Segundos até poder enviar de novo. 0 = livre."""
    ate = db.get_ajuste("throttle_until")
    if not ate:
        return 0.0
    try:
        fim = calendar.timegm(time.strptime(ate, "%Y-%m-%dT%H:%M:%SZ"))
    except ValueError:
        return 0.0
    return max(0.0, fim - time.time())


def _codigo_erro(body) -> int:
    if isinstance(body, dict):
        try:
            return int((body.get("error") or {}).get("code") or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def _espera_sugerida(headers) -> float:
    """Quanto esperar, segundo a própria Meta. O header X-Business-Use-Case-Usage
    traz estimated_time_to_regain_access em MINUTOS. Sem header, cai no padrão."""
    try:
        uso = _json.loads(headers.get("X-Business-Use-Case-Usage", ""))
        minutos = max((item.get("estimated_time_to_regain_access", 0) or 0)
                      for lista in uso.values() for item in lista)
        if minutos > 0:
            return minutos * 60.0
    except (ValueError, AttributeError, TypeError):
        pass
    return COOLDOWN_PADRAO_S


def _entra_em_cooldown(segundos: float, origem: str) -> None:
    ja_estava = cooldown_restante() > 0
    db.set_ajuste("throttle_until", db.in_seconds_iso(segundos))
    db.log_event("throttle_meta", payload={"segundos": int(segundos), "origem": origem})
    if not ja_estava:
        # só na entrada do episódio: um aviso por throttle, não um por mensagem presa
        alerta.avisar(f"CEQ segurou os envios: rate limit da Meta ({origem}). "
                      f"Fila reagendada, volta em ~{max(1, int(segundos / 60))} min.")


def post_with_retry(url, access_token, payload, timeout=30):
    """POST com detecção de throttle da Meta e 1 retry em erro transitório.

    Retorna (ok, status, body). ok=None não é falha: significa "não enviei porque a
    instância está em cooldown"; o chamador reagenda em vez de descartar.
    """
    resta = cooldown_restante()
    if resta > 0:
        return None, 0, f"cooldown {int(resta)}s"
    for attempt in (1, 2):
        try:
            r = requests.post(url, json=payload,
                              headers={"Authorization": f"Bearer {access_token}"}, timeout=timeout)
            body = (r.json() if r.headers.get("content-type", "").startswith("application/json")
                    else r.text[:400])
            if r.status_code == 200:
                return True, r.status_code, body
            # throttle de verdade costuma vir num HTTP 400/403 com o código no corpo,
            # que o retry cego de antes nunca resolveria. Aqui não se insiste.
            if _codigo_erro(body) in CODIGOS_THROTTLE or r.status_code == 429:
                _entra_em_cooldown(_espera_sugerida(r.headers), f"http {r.status_code}")
                return None, r.status_code, body
            if r.status_code in (500, 503) and attempt == 1:
                time.sleep(10)
                continue
            return False, r.status_code, body
        except requests.RequestException as e:
            if attempt == 2:
                return False, 0, sem_segredo(e)
            time.sleep(5)
    return False, 0, "unreachable"


def send_private_reply(account, comment_id, text):
    return post_with_retry(f"{GRAPH}/{account['ig_id']}/messages", account["access_token"],
                           {"recipient": {"comment_id": comment_id}, "message": {"text": text}})


def send_dm(account, recipient_id, text):
    return post_with_retry(f"{GRAPH}/{account['ig_id']}/messages", account["access_token"],
                           {"recipient": {"id": recipient_id}, "message": {"text": text}})


def send_public_reply(account, comment_id, text):
    return post_with_retry(f"{GRAPH}/{comment_id}/replies", account["access_token"],
                           {"message": text})


# ---------- mensagens ricas (motor de fluxo) ----------
#
# Todas recebem `recipient`, que é {"id": igsid} pra DM ou {"comment_id": ...} pra
# private reply. Assim o mesmo nó do fluxo serve tanto pra primeira resposta a um
# comentário quanto pra continuação da conversa no direct.

TEXT_LIMIT = 1000          # bytes, limite da Meta
MAX_BUTTONS = 3            # por cartão do generic template
MAX_QUICK_REPLIES = 13
MAX_CAROUSEL = 10
LIMITE_TITULO_CARD = 80    # título do generic template (carrossel), limite da Meta
LIMITE_TEXTO_BOTOES = 640  # texto do button template, limite da Meta
LIMITE_TITULO_BOTAO = 20   # recomendação da Meta; acima disso o app corta na tela


def _send(account, recipient, message):
    return post_with_retry(f"{GRAPH}/{account['ig_id']}/messages", account["access_token"],
                           {"recipient": recipient, "message": message})


def truncate(text: str, limit: int = TEXT_LIMIT) -> str:
    """Corta no limite de bytes da Meta sem partir caractere nem palavra no meio."""
    raw = (text or "").encode("utf-8")
    if len(raw) <= limit:
        return text or ""
    cut = raw[:limit].decode("utf-8", errors="ignore")
    espaco = cut.rfind(" ")
    return (cut[:espaco] if espaco > limit * 0.6 else cut).rstrip()


def send_text(account, recipient, text):
    return _send(account, recipient, {"text": truncate(text)})


def send_buttons(account, recipient, text, buttons):
    """Até 3 botões. Cada um é {"title", "type": "url"|"postback", "url"|"key"}.

    Botão de link vira web_url; botão de resposta vira postback, e o `key` volta
    pra gente no webhook messaging_postbacks pra casar com a aresta do nó.
    """
    payload_buttons = []
    for b in (buttons or [])[:MAX_BUTTONS]:
        titulo = truncate(b.get("title") or b.get("label") or "", LIMITE_TITULO_BOTAO)
        if b.get("type") == "url" or b.get("url"):
            payload_buttons.append({"type": "web_url", "url": b.get("url", ""), "title": titulo})
        else:
            payload_buttons.append({"type": "postback", "title": titulo,
                                    "payload": b.get("key") or titulo})
    if not payload_buttons:
        return send_text(account, recipient, text)

    # Button template, que é o formato que junta texto e botões numa mensagem só.
    # O teto de texto aqui é 640 caracteres (o da mensagem comum é 1000), então o que
    # passar disso vai antes, como mensagem normal, pra não sumir no truncamento.
    #
    # Nota de campo: botão NÃO aparece no Instagram Web, só no app do celular. É
    # limitação da plataforma, vale pra qualquer ferramenta (o ManyChat sofre igual).
    # Quem testar pelo computador vai achar que está quebrado sem estar.
    texto = (text or "").strip()
    antes = ""
    if len(texto) > LIMITE_TEXTO_BOTOES:
        corte = texto.rfind("\n", 0, LIMITE_TEXTO_BOTOES) or LIMITE_TEXTO_BOTOES
        antes, texto = texto[:corte].strip(), texto[corte:].strip()

    if antes:
        ok, status, body = send_text(account, recipient, antes)
        if not ok:
            return ok, status, body
        time.sleep(0.6)   # a ordem importa: o card tem que chegar depois do texto

    return _send(account, recipient, {
        "attachment": {"type": "template", "payload": {
            "template_type": "button", "text": truncate(texto, LIMITE_TEXTO_BOTOES),
            "buttons": payload_buttons}}})


def send_quick_replies(account, recipient, text, options):
    """Até 13 opções. Cada uma é {"title", "key"}; o key volta como quick_reply.payload."""
    qrs = [{"content_type": "text",
            "title": truncate(o.get("title") or o.get("label") or "", 20),
            "payload": o.get("key") or o.get("title") or ""}
           for o in (options or [])[:MAX_QUICK_REPLIES]]
    if not qrs:
        return send_text(account, recipient, text)
    return _send(account, recipient, {"text": truncate(text), "quick_replies": qrs})


def send_media(account, recipient, url, kind="image"):
    """kind: image | video | audio. A URL precisa ser pública e acessível pela Meta."""
    if kind not in ("image", "video", "audio"):
        kind = "image"
    return _send(account, recipient, {
        "attachment": {"type": kind, "payload": {"url": url, "is_reusable": True}}})


def send_carousel(account, recipient, elements):
    """Carrossel (generic template). Cada elemento é {"title", "image_url", "subtitle",
    "url", "buttons"}. Até 10 cartões."""
    payload_elements = []
    for e in (elements or [])[:MAX_CAROUSEL]:
        el = {"title": truncate(e.get("title", ""), 80)}
        if e.get("image_url"):
            el["image_url"] = e["image_url"]
        if e.get("subtitle"):
            el["subtitle"] = truncate(e["subtitle"], 80)
        if e.get("url"):
            el["default_action"] = {"type": "web_url", "url": e["url"]}
        botoes = []
        for b in (e.get("buttons") or [])[:MAX_BUTTONS]:
            titulo = truncate(b.get("title") or b.get("label") or "", LIMITE_TITULO_BOTAO)
            if b.get("type") == "url" or b.get("url"):
                botoes.append({"type": "web_url", "url": b.get("url", ""), "title": titulo})
            else:
                botoes.append({"type": "postback", "title": titulo,
                               "payload": b.get("key") or titulo})
        if botoes:
            el["buttons"] = botoes
        payload_elements.append(el)
    if not payload_elements:
        return False, 0, "carrossel vazio"
    return _send(account, recipient, {
        "attachment": {"type": "template", "payload": {
            "template_type": "generic", "elements": payload_elements}}})


def fetch_media_list(access_token, limit=25):
    """Posts e Reels da conta — alimenta o seletor de 'post específico' no editor."""
    try:
        r = requests.get(f"{GRAPH}/me/media", params={
            "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp",
            "limit": limit, "access_token": access_token}, timeout=20)
        if r.status_code == 200:
            return r.json().get("data", [])
    except requests.RequestException:
        pass
    return []
