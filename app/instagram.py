"""Cliente da API do Instagram, nos dois jeitos de conectar que a Meta oferece.

- `instagram_login` (o de sempre): login do Instagram, Graph em graph.instagram.com,
  token do Instagram de 60 dias que a instância renova sozinha.
- `facebook_login` (1.11.0): o login unificado que a Meta impõe aos apps novos
  (Facebook Login para Empresas com `config_id`). Graph em graph.facebook.com, com o
  ID da conta profissional no caminho. O token é do sistema da empresa (Business
  Integration System User), sem renovação de 60 dias. O mesmo modo cobre o caminho
  clássico "API do Instagram com login do Facebook" (página do Facebook ligada à
  conta), em que o token é o da página.

Cada conta guarda o próprio modo (`accounts.api_modo`). Toda função que fala com a
Meta recebe a conta e tira dela a base, o token e o nó certo; conta antiga, sem
coluna preenchida, segue exatamente pelo caminho de antes.
"""
import calendar
import json as _json
import logging
import re
import time
from urllib.parse import urlencode

import requests

from . import alerta, db

log = logging.getLogger(__name__)

GRAPH = "https://graph.instagram.com/v23.0"
OAUTH_AUTHORIZE = "https://www.instagram.com/oauth/authorize"
OAUTH_TOKEN = "https://api.instagram.com/oauth/access_token"
SCOPES = "instagram_business_basic,instagram_business_manage_messages,instagram_business_manage_comments"

# Login unificado / login do Facebook. Mesma versão da Graph do resto do código.
GRAPH_FB = "https://graph.facebook.com/v23.0"
FB_DIALOG = "https://www.facebook.com/v23.0/dialog/oauth"
# Só usados quando o app não tem `config_id` (app antigo com "login do Facebook"
# clássico). Com config_id, quem decide as permissões é a configuração na Meta.
SCOPES_FB = ("instagram_basic,instagram_manage_messages,instagram_manage_comments,"
             "pages_show_list,pages_read_engagement,pages_manage_metadata,business_management")

MODO_IG = "instagram_login"
MODO_FB = "facebook_login"
MODOS = (MODO_IG, MODO_FB)

# Campos de webhook assinados por conta. No login unificado a doc lista estes quatro
# (comments, live_comments, messages, messaging_postbacks) com as permissões
# instagram_manage_comments / instagram_manage_messages.
CAMPOS_WEBHOOK = "comments,live_comments,messages,messaging_postbacks"
# Caminho da página: a assinatura é da PÁGINA no app; os campos do Instagram em si
# são os marcados no painel da Meta. `feed` só liga a página ao app (pede
# pages_manage_metadata, que já está nos scopes).
CAMPOS_WEBHOOK_PAGINA = "feed"


def modo(account) -> str:
    """Modo de conexão da conta. Vazio (conta de antes da 1.11) = login do Instagram."""
    m = (account or {}).get("api_modo") or MODO_IG
    return m if m in MODOS else MODO_IG


def e_fb(account) -> bool:
    return modo(account) == MODO_FB


def base(account) -> str:
    return GRAPH_FB if e_fb(account) else GRAPH


def no_ig(account) -> str:
    """ID da conta profissional pra pôr no caminho. No login do Instagram é o `ig_id`
    (o que o código sempre usou); no do Facebook, o ID 1784... que a Meta devolveu."""
    if e_fb(account):
        return str(account.get("ig_user_id") or account.get("ig_id") or "")
    return str(account["ig_id"])


def no_mensagens(account) -> str:
    """Quem envia a DM. Caminho da página: /{page-id}/messages com o token da
    página (doc do Messenger para Instagram). Login unificado e login do Instagram:
    /{ig-id}/messages."""
    if e_fb(account) and account.get("page_id"):
        return str(account["page_id"])
    return no_ig(account)


def _conta_e_token(conta_ou_token):
    """Aceita a conta (dict) ou, como antes da 1.11, só o token do Instagram."""
    if isinstance(conta_ou_token, dict):
        return conta_ou_token, conta_ou_token.get("access_token", "")
    return {}, conta_ou_token or ""


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


# ---------- login unificado / login do Facebook ----------

class SemContaInstagram(Exception):
    """A autorização deu certo, mas nenhuma conta profissional do Instagram veio
    junto. A mensagem é pra tela do dono, sem nada técnico nem segredo."""


def authorize_url_fb(app_id: str, redirect_uri: str, state: str, config_id: str = "") -> str:
    """Diálogo do Facebook Login para Empresas.

    Com `config_id` (o caso de todo app novo): a configuração decide permissões e
    ativos, e `scope` não vai (a doc do login unificado não usa; apps novos
    respondem "Invalid Scopes" a ele). `prompt=login` mostra as duas opções de
    entrada, Facebook e Instagram, em vez de seguir calado com o Facebook já aberto
    no navegador. Sem `config_id`: login do Facebook clássico, com a lista de scopes.
    """
    params = {"client_id": app_id, "redirect_uri": redirect_uri,
              "response_type": "code", "state": state}
    if config_id:
        params.update(config_id=config_id, prompt="login")
    else:
        params["scope"] = SCOPES_FB
    return f"{FB_DIALOG}?{urlencode(params)}"


def _expira_em(expires_in):
    try:
        segundos = int(expires_in or 0)
    except (TypeError, ValueError):
        segundos = 0
    if segundos <= 0:
        return None   # sem prazo (token do sistema "Nunca" ou token de página)
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + segundos))


def _corpo(r):
    try:
        corpo = r.json()
    except ValueError:
        return {}
    return corpo if isinstance(corpo, dict) else {}


def _get_fb(caminho, token, **params):
    r = requests.get(f"{GRAPH_FB}/{caminho}", params={**params, "access_token": token},
                     timeout=30)
    return r.status_code, _corpo(r)


TOKEN_CURTO_SEGUNDOS = 86400   # abaixo de 1 dia é token de usuário curto (1-2h)


def _token_longo(app_id, app_secret, tok: dict) -> dict:
    """Token de usuário curto vira longo (60 dias) antes de ser usado ou salvo.

    Sem expires_in (ou 0) é token do usuário do sistema, que não vence: fica como
    veio. Se a troca falhar, segue com o curto (melhor que nada) e só o motivo,
    sem segredo, vai pro log."""
    try:
        segundos = int(tok.get("expires_in") or 0)
    except (TypeError, ValueError):
        segundos = 0
    if not (0 < segundos < TOKEN_CURTO_SEGUNDOS):
        return tok
    try:
        r = requests.get(f"{GRAPH_FB}/oauth/access_token", params={
            "grant_type": "fb_exchange_token", "client_id": app_id,
            "client_secret": app_secret, "fb_exchange_token": tok["access_token"]},
            timeout=30)
    except requests.RequestException as e:
        log.warning("troca por token longo falhou: %s", sem_segredo(e))
        return tok
    novo = _corpo(r)
    if r.status_code != 200 or not novo.get("access_token"):
        log.warning("troca por token longo falhou: http %s", r.status_code)
        return tok
    # token longo de usuário vale 60 dias; se a Meta não disser, assume isso
    return {**tok, "access_token": novo["access_token"],
            "expires_in": novo.get("expires_in") or 5184000}


def exchange_code_fb(app_id, app_secret, redirect_uri, code) -> list:
    """code -> token -> contas do Instagram que o dono liberou. Devolve a lista de
    candidatas, cada uma pronta pra virar conta:
      {ig_user_id, username, page_id, page_nome, access_token, token_expires_at}

    1. Login unificado (app novo): o token é do sistema da empresa e as contas vêm
       de /me/assigned_instagram_accounts. Sem página, sem renovação de 60 dias.
    2. Se não vier conta por ali, é o login do Facebook clássico: o token é de
       usuário, vira token longo, e as contas vêm das páginas (/me/accounts) que têm
       instagram_business_account. Token de página tirado de token longo não vence.
    """
    r = requests.get(f"{GRAPH_FB}/oauth/access_token", params={
        "client_id": app_id, "client_secret": app_secret,
        "redirect_uri": redirect_uri, "code": code}, timeout=30)
    r.raise_for_status()
    tok = _token_longo(app_id, app_secret, r.json())
    token = tok["access_token"]

    status, corpo = _get_fb("me/assigned_instagram_accounts", token,
                            fields="id,username", limit=100)
    contas = [c for c in (corpo.get("data") or []) if c.get("id")] if status == 200 else []
    if contas:
        expira = _expira_em(tok.get("expires_in"))
        return [{"ig_user_id": str(c["id"]), "username": c.get("username", ""),
                 "page_id": "", "page_nome": "", "access_token": token,
                 "token_expires_at": expira} for c in contas]

    # caminho clássico: token de usuário -> longo -> páginas
    longo = token
    r2 = requests.get(f"{GRAPH_FB}/oauth/access_token", params={
        "grant_type": "fb_exchange_token", "client_id": app_id,
        "client_secret": app_secret, "fb_exchange_token": token}, timeout=30)
    if r2.status_code == 200:
        longo = _corpo(r2).get("access_token") or token
    status, corpo = _get_fb("me/accounts", longo,
                            fields="id,name,access_token,instagram_business_account",
                            limit=100)
    candidatas = []
    for pg in (corpo.get("data") or []) if status == 200 else []:
        ig = (pg.get("instagram_business_account") or {}).get("id")
        if not (ig and pg.get("access_token")):
            continue
        _, perfil = _get_fb(str(ig), pg["access_token"], fields="username")
        candidatas.append({"ig_user_id": str(ig), "username": perfil.get("username", ""),
                           "page_id": str(pg.get("id", "")), "page_nome": pg.get("name", ""),
                           "access_token": pg["access_token"], "token_expires_at": None})
    if not candidatas:
        raise SemContaInstagram(
            "A Meta autorizou, mas nenhuma conta profissional do Instagram veio junto. "
            "Na tela da Meta, escolha o portfólio empresarial e marque a conta do "
            "Instagram. Se ela não aparece, confira se é conta Profissional (Empresa ou "
            "Criador) e, no app da Meta, se a configuração do login inclui a permissão "
            "business_management.")
    return candidatas


def subscribe_webhooks(conta_ou_token, fields=CAMPOS_WEBHOOK):
    """live_comments só notifica durante a transmissão; messaging_postbacks traz o
    clique em botão do fluxo. Ambos exigem que o app esteja publicado.

    Login do Instagram: /me/subscribed_apps no graph.instagram.com. Login unificado:
    /{ig-id}/subscribed_apps no graph.facebook.com com o token do sistema. Caminho
    da página: /{page-id}/subscribed_apps com o token da página."""
    conta, access_token = _conta_e_token(conta_ou_token)
    if e_fb(conta):
        if conta.get("page_id"):
            url, fields = f"{GRAPH_FB}/{conta['page_id']}/subscribed_apps", CAMPOS_WEBHOOK_PAGINA
        else:
            url = f"{GRAPH_FB}/{no_ig(conta)}/subscribed_apps"
        r = requests.post(url, data={"subscribed_fields": fields,
                                     "access_token": access_token}, timeout=30)
        _confere_token(conta, _corpo(r), access_token)
        return r.status_code == 200, sem_segredo(r.text[:300])
    r = requests.post(f"{GRAPH}/me/subscribed_apps", params={
        "subscribed_fields": fields, "access_token": access_token}, timeout=30)
    return r.status_code == 200, r.text[:300]


# ---------- token que a Meta derrubou (erro 190) ----------
#
# No login unificado não há renovação: o token vale até o dono tirar o app do
# portfólio, mudar a conta de portfólio ou a Meta revogar. Aí a Meta responde 190,
# e insistir não resolve: o painel passa a pedir "Reconectar". Conta no login do
# Instagram não usa essa marca (lá o refresh de 60 dias segue como sempre).

CODIGO_TOKEN_INVALIDO = 190


def _confere_token(conta, body, token_usado=None) -> None:
    """Marca a conta pra reconectar no 190, mas só se o token que levou o 190 ainda
    é o da conta. Envio ou verificação em voo com o dict de antes da reconexão
    recebe 190 do token velho e não pode derrubar o token novo."""
    if not (conta and e_fb(conta) and conta.get("id")):
        return
    if _codigo_erro(body) != CODIGO_TOKEN_INVALIDO:
        return
    atual = db.get_account(conta["id"])
    usado = token_usado or conta.get("access_token")
    if not atual or not usado or atual.get("access_token") != usado:
        return
    if not token_invalido(conta):
        msg = str(((body or {}).get("error") or {}).get("message", ""))
        db.log_event("token_invalido", conta["id"], ok=False,
                     payload={"detalhe": sem_segredo(msg)[:200]})
    db.set_ajuste(f"token_invalido:{conta['id']}", db.in_seconds_iso(0))


def token_invalido(conta) -> bool:
    return bool(conta and conta.get("id") and db.get_ajuste(f"token_invalido:{conta['id']}"))


def limpa_token_invalido(conta_id) -> None:
    db.set_ajuste(f"token_invalido:{conta_id}", "")


def verificar_token(conta) -> bool:
    """Leitura barata pra descobrir token derrubado sem esperar o próximo envio.
    Só no login do Facebook; devolve True se a Meta aceitou."""
    if not e_fb(conta):
        return True
    try:
        status, corpo = _get_fb(no_ig(conta), conta["access_token"], fields="username")
    except requests.RequestException:
        return True   # rede fora não é token inválido
    _confere_token(conta, corpo)
    if status == 200:
        limpa_token_invalido(conta["id"])
    return status == 200


def token_status(conta) -> dict:
    """Situação do acesso pro painel, /health, MCP e ping do chão:
    {valido, dias (None = sem prazo), renova (o CEQ renova sozinho?)}."""
    if not conta:
        return {"valido": False, "dias": None, "renova": False}
    if e_fb(conta):
        dias = token_days_left(conta) if conta.get("token_expires_at") else None
        valido = not token_invalido(conta) and (dias is None or dias > 0)
        return {"valido": valido, "dias": dias, "renova": False}
    dias = token_days_left(conta)
    return {"valido": dias > 0, "dias": dias, "renova": True}


def refresh_token(account: dict) -> tuple:
    """Renova token longo (precisa ter 24h+ de idade). Retorna (ok, detalhe).
    Só existe no login do Instagram: no do Facebook não há o que renovar."""
    if e_fb(account):
        return False, "sem renovação no login do Facebook"
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


def fetch_own_pic(conta_ou_token) -> str:
    """Foto de perfil da própria conta conectada. No login do Facebook, /me é o
    usuário do sistema (ou a página): a foto vem do nó da conta do Instagram."""
    conta, access_token = _conta_e_token(conta_ou_token)
    no = no_ig(conta) if e_fb(conta) else "me"
    try:
        r = requests.get(f"{base(conta)}/{no}", params={
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


def fetch_profile(conta_ou_token, igsid) -> dict:
    """Perfil de quem interage (User Profile API): nome, @, foto, seguidores, segue-você.
    Retorna {} se a API não permitir (ex.: alguns comentaristas)."""
    conta, access_token = _conta_e_token(conta_ou_token)
    try:
        r = requests.get(f"{base(conta)}/{igsid}", params={
            "fields": "name,username,profile_pic,follower_count,is_user_follow_business",
            "access_token": access_token}, timeout=15)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return {}


def fetch_username(conta_ou_token, igsid) -> str:
    conta, access_token = _conta_e_token(conta_ou_token)
    try:
        r = requests.get(f"{base(conta)}/{igsid}", params={
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


def post_with_retry(url, access_token, payload, timeout=30, conta=None):
    """POST com detecção de throttle da Meta e 1 retry em erro transitório.

    Retorna (ok, status, body). ok=None não é falha: significa "não enviei porque a
    instância está em cooldown"; o chamador reagenda em vez de descartar.
    Com `conta` no login do Facebook, erro 190 marca a conta pra reconectar.
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
            _confere_token(conta, body, access_token)
            if r.status_code in (500, 503) and attempt == 1:
                time.sleep(10)
                continue
            return False, r.status_code, body
        except requests.RequestException as e:
            if attempt == 2:
                return False, 0, sem_segredo(e)
            time.sleep(5)
    return False, 0, "unreachable"


def _url_mensagens(account) -> str:
    return f"{base(account)}/{no_mensagens(account)}/messages"


def send_private_reply(account, comment_id, text):
    return post_with_retry(_url_mensagens(account), account["access_token"],
                           {"recipient": {"comment_id": comment_id}, "message": {"text": text}},
                           conta=account)


def send_dm(account, recipient_id, text):
    return post_with_retry(_url_mensagens(account), account["access_token"],
                           {"recipient": {"id": recipient_id}, "message": {"text": text}},
                           conta=account)


def send_public_reply(account, comment_id, text):
    return post_with_retry(f"{base(account)}/{comment_id}/replies", account["access_token"],
                           {"message": text}, conta=account)


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
    return post_with_retry(_url_mensagens(account), account["access_token"],
                           {"recipient": recipient, "message": message}, conta=account)


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


def fetch_media_list(conta_ou_token, limit=25):
    """Posts e Reels da conta — alimenta o seletor de 'post específico' no editor."""
    conta, access_token = _conta_e_token(conta_ou_token)
    no = no_ig(conta) if e_fb(conta) else "me"
    try:
        r = requests.get(f"{base(conta)}/{no}/media", params={
            "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp",
            "limit": limit, "access_token": access_token}, timeout=20)
        if r.status_code == 200:
            return r.json().get("data", [])
    except requests.RequestException:
        pass
    return []
