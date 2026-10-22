"""comenta EU QUERO — automação open de comentário/story/DM -> resposta no direct.

Endpoints públicos:  /webhook  /privacy  /health
Painel (senha):      /login  /painel  /fluxos  /editor  /leads  /auth/start  /auth/callback
"""
import asyncio
import contextlib
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import threading
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import (FileResponse, HTMLResponse, PlainTextResponse,
                               RedirectResponse)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import alerta, api, db, flowengine, instagram, mcp_server, runtime, segredos, whatsapp
from .senha import conferir_senha, definir_senha, senha_definida  # noqa: F401

VERIFY_TOKEN = os.environ.get("WEBHOOK_VERIFY_TOKEN", "troque-este-token")
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
CLUB_TOKEN = os.environ.get("CLUB_TOKEN", "")


# ID e chave secreta do app da Meta: o .env tem precedência (instâncias antigas);
# sem ele, valem os que o dono colou em /config (cifrados em `ajustes`). Funções e
# não constantes, porque mudam ao vivo quando o dono salva a configuração.
def meta_app_id() -> str:
    return os.environ.get("META_APP_ID", "") or segredos.ler("meta_app_id")


def meta_app_secret() -> str:
    return os.environ.get("META_APP_SECRET", "") or segredos.ler("meta_app_secret")


# O WhatsApp assina o webhook com a chave secreta do app GERAL da Meta; a do campo
# acima é a do produto Instagram. São duas, e o /webhook aceita qualquer uma.
def meta_wa_app_secret() -> str:
    return os.environ.get("META_WA_APP_SECRET", "") or segredos.ler("meta_wa_app_secret")

# Token do primeiro acesso: abre /instalar uma vez, enquanto não existe senha.
SETUP_TOKEN = os.environ.get("CEQ_SETUP_TOKEN", "")


def _int_env(nome, padrao=0):
    try:
        return int(os.environ.get(nome, "") or padrao)
    except ValueError:
        return padrao


# retenção de dados: 0 = guardar pra sempre (padrão, pra ninguém perder dado sem pedir)
RETENCAO_LEADS_DIAS = _int_env("RETENCAO_LEADS_DIAS")
RETENCAO_EVENTOS_DIAS = _int_env("RETENCAO_EVENTOS_DIAS")
ACTIVATION_URL = os.environ.get("ACTIVATION_URL", "https://ia.augustogobatto.com/api/ceq/validate")
# Central do chão. Instalação nova (token inst_) manda o ping pra lá; a antiga (club_)
# continua no ACTIVATION_URL.
CHAO_URL = os.environ.get("CHAO_URL", "https://ia.augustogobatto.com").rstrip("/")

# Versão do produto. Sobe junto com mudança que o dono da instância percebe.
VERSAO = "1.8.0"


# Ativação (modo aviso): nunca bloqueia a ferramenta — só informa o status no painel.
LICENSE = {"status": "sem_token" if not CLUB_TOKEN else "verificando", "member": None}


def _saude() -> dict:
    """Sinais de vida que vão no ping do chão. Só contagem e data: nenhum dado de
    lead, nenhum token. Cada item é independente: um que falhe não derruba o ping."""
    saude = {}
    try:
        saude["leads"] = db.conn().execute("select count(*) from leads").fetchone()[0]
    except Exception:
        pass
    try:
        saude["db_mb"] = (round(os.path.getsize(db.DB_PATH) / 1048576, 1)
                          if os.path.exists(db.DB_PATH) else 0)
    except Exception:
        pass
    try:
        kinds = list(db.KINDS_ENVIO)
        saude["ultima_entrega"] = db.conn().execute(
            f"select max(ts) from events where ok=1 and kind in ({','.join('?' * len(kinds))})",
            kinds).fetchone()[0]
    except Exception:
        pass
    try:
        account = db.first_account()
        saude["token_meta_dias"] = (round(instagram.token_days_left(account), 1)
                                    if account else None)
    except Exception:
        pass
    return saude


def check_license():
    """Confere a assinatura e, de passagem, diz quem é esta instância.

    O `produto` existe porque o token club_ é o mesmo do "Conectar seu Claude": sem
    ele, não dava pra separar uma instância do CEQ de alguém usando o MCP no Claude.
    A `instancia` é um id aleatório criado no primeiro boot e guardado no banco
    local — serve pra contar instalações sem identificar conta do Instagram.

    Token inst_ (instalação pelo chão) vai pro /api/chao/ping da central, com a
    saúde da instância; club_ segue no /api/ceq/validate. Nos dois casos, licença
    inativa só muda o aviso do painel: nada para de funcionar.
    """
    import requests as _rq
    if not CLUB_TOKEN:
        LICENSE.update(status="sem_token", member=None)
        return
    if CLUB_TOKEN.startswith("inst_"):
        corpo = {
            "token": CLUB_TOKEN,
            "versao_chao": os.environ.get("CHAO_VERSAO", ""),
            "pacotes": {"ceq": {"versao": VERSAO}},
            "saude": _saude(),
        }
        url = CHAO_URL + "/api/chao/ping"
    else:
        corpo = {
            "token": CLUB_TOKEN,
            "produto": "ceq",
            "versao": VERSAO,
            "instancia": db.id_da_instancia(),
        }
        url = ACTIVATION_URL
    try:
        data = _rq.post(url, json=corpo, timeout=15).json()
        ativa = data.get("ativa") if "ativa" in data else data.get("active")
        if ativa:
            LICENSE.update(status="ativada", member=data.get("membro") or data.get("member"))
        else:
            LICENSE.update(status="nao_ativada", member=None)
    except Exception:
        if LICENSE["status"] == "verificando":
            LICENSE.update(status="erro_rede")
        # falha de rede não derruba status já conhecido

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@contextlib.asynccontextmanager
async def _ciclo(_app):
    """Ciclo de vida: o startup de sempre e o transporte do MCP (o SDK precisa do
    gerente de sessão rodando enquanto o app está no ar)."""
    await startup()
    async with mcp_server.rodando():
        yield


app = FastAPI(title="comenta EU QUERO", lifespan=_ciclo)
app.include_router(api.router)
app.include_router(mcp_server.router)

# O editor é um app Vue já compilado (o build do Vite sai direto aqui). Não tem
# node rodando em produção: são arquivos estáticos e pronto.
STATIC_DIR = Path(__file__).parent / "static"
EDITOR_INDEX = STATIC_DIR / "editor" / "index.html"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _fmt_k(n):
    """1371786 -> 1,4M · 9713 -> 9,7k · 886 -> 886 · None -> —"""
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".", ",")
    if n >= 1_000:
        return f"{n / 1_000:.1f}k".replace(".", ",")
    return str(n)


templates.env.filters["fmt_k"] = _fmt_k


def wa_ativo() -> bool:
    """Menu e telas de WhatsApp só aparecem com número ligado. Sem ele, o painel é o
    de sempre."""
    try:
        return whatsapp.configurado(db.first_account())
    except Exception:
        return False


templates.env.globals["wa_ativo"] = wa_ativo

# Versão do CSS pelo conteúdo: muda a cada deploy que mexe no arquivo, e o
# navegador nunca fica preso num ceq.css velho do cache.
_CSS = STATIC_DIR / "ceq.css"
templates.env.globals["css_v"] = (hashlib.sha1(_CSS.read_bytes()).hexdigest()[:10]
                                  if _CSS.exists() else "0")


def wa_estado(account) -> dict:
    """Estado do número pro painel, pra /config e pra /api/wa/estado. Nunca leva
    token: só o que a Meta mostra publicamente do número e as contagens locais."""
    if not whatsapp.configurado(account):
        return {"configurado": False}
    return {"configurado": True,
            "numero": account.get("wa_numero") or "",
            "nome": account.get("wa_nome") or "",
            "qualidade": account.get("wa_qualidade") or "",
            "limite": account.get("wa_limite"),
            "enviados_24h": db.templates_enviados_24h(account["id"]),
            "cooldown_s": int(whatsapp.cooldown_restante()),
            "atualizado_em": account.get("wa_estado_ts") or ""}


def _atualizar_estado_wa():
    """Relê nome, qualidade e limite de cada número ligado. Roda no boot e a cada
    ciclo do refresh de token; conta sem WA não gera chamada nenhuma."""
    for account in db.all_accounts():
        if not whatsapp.configurado(account):
            continue
        try:
            info = whatsapp.fetch_phone_info(account)
            if info:
                db.update_wa_estado(account["id"], info["numero"], info["nome"],
                                    info["qualidade"], info["limite"])
        except Exception as e:
            db.log_event("wa_estado", account["id"], ok=False,
                         payload={"erro": instagram.sem_segredo(e)[:200]})


# ---------- sessão do painel ----------

COOKIE_SEGURO = BASE_URL.startswith("https://")


def logged_in(request: Request) -> bool:
    if not senha_definida():
        return False
    return db.sessao_valida(request.cookies.get("ceq_session", ""))


def require_login(request: Request):
    if not logged_in(request):
        return RedirectResponse("/login", status_code=303)
    return None


# ---------- freio de força bruta no login ----------
#
# A senha do painel é a única coisa entre a internet e a conta de Instagram
# conectada. Sem freio, dá pra testar senha a noite inteira sem deixar rastro.
# Contagem por IP, na memória: some no restart, o que é aceitável — o objetivo é
# tornar a tentativa em massa lenta, não manter histórico forense.

LOGIN_TENTATIVAS = {}          # ip -> [falhas, bloqueado_ate]
LOGIN_LIMITE = 5               # falhas antes de começar a travar
LOGIN_ESPERA_BASE = 30         # segundos, dobrando a cada falha depois do limite
LOGIN_ESPERA_MAX = 15 * 60
LOGIN_IPS_MAX = 5000           # teto do dicionário: acima disso, joga fora quem já expirou

# Teto que não depende de IP. O freio por IP sozinho não segura quem troca de
# endereço a cada tentativa (botnet, proxy rotativo): somadas, as falhas de todos os
# IPs também têm limite. O preço é que um ataque em andamento pode deixar o dono
# esperando a janela pra entrar; quem já está logado não é afetado.
LOGIN_GLOBAL_LIMITE = _int_env("CEQ_LOGIN_FALHAS_JANELA", 30)
LOGIN_GLOBAL_JANELA = 10 * 60
LOGIN_FALHAS_GLOBAIS = []      # instantes das últimas falhas, de qualquer IP
LOGIN_LOCK = threading.Lock()


def _e_proxy(host: str) -> bool:
    """A conexão veio de um proxy na mesma máquina ou rede privada (nginx, cloudflared,
    traefik do Docker)? Só nesse caso o X-Forwarded-For merece leitura."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


def _ip_de(request: Request) -> str:
    """IP de quem está do outro lado, sem confiar no que o cliente escreve.

    O X-Forwarded-For é uma lista que cada proxy vai completando no FIM. O começo é
    texto livre de quem fez a requisição: usar o primeiro item (como era antes)
    deixava o atacante escolher um IP novo a cada tentativa e nunca ser bloqueado,
    ou escolher o IP do dono e trancá-lo pra fora. O último item é o que o nosso
    proxy viu de verdade. E só vale ler o cabeçalho quando a conexão chegou por um
    proxy; exposto direto, o cabeçalho inteiro é do cliente e o que conta é o socket.
    """
    socket = request.client.host if request.client else "?"
    if not _e_proxy(socket):
        return socket
    itens = [i.strip() for i in request.headers.get("x-forwarded-for", "").split(",") if i.strip()]
    if not itens:
        return socket
    try:
        return str(ipaddress.ip_address(itens[-1]))
    except ValueError:
        return socket


# ---------- senha nunca em claro ----------
#
# A instalação exige HTTPS de qualquer jeito (a Meta só entrega webhook em URL
# https), mas o compose publicava a porta 8080 em 0.0.0.0 além do proxy. Sobrava um
# caminho paralelo em HTTP puro pelo IP do servidor, e quem entrasse por ali mandava
# a senha do painel legível na rede. Fechar a porta no compose só vale pra quem
# instalar de novo; esta checagem viaja na imagem e alcança quem já está rodando.
#
# Liberado quando o acesso é local (túnel SSH, curl no próprio servidor), porque aí
# nada trafega fora da máquina. CEQ_PERMITE_HTTP=1 é a saída de emergência pra quem
# tem proxy que não manda X-Forwarded-Proto: destrava sem precisar editar código.

PERMITE_HTTP = os.environ.get("CEQ_PERMITE_HTTP", "") == "1"
_LOCAIS = {"127.0.0.1", "::1", "localhost"}


def conexao_insegura(request: Request) -> bool:
    """True quando a senha viajaria em claro nesta requisição."""
    if PERMITE_HTTP or not COOKIE_SEGURO:
        return False
    esquema = (request.headers.get("x-forwarded-proto", "")
               or request.url.scheme).split(",")[0].strip().lower()
    if esquema == "https":
        return False
    cliente = request.client.host if request.client else ""
    host = (request.url.hostname or "").lower()
    return not (cliente in _LOCAIS and host in _LOCAIS)


AVISO_HTTP = ("Esta página foi aberta por HTTP, sem criptografia: a senha iria "
              "legível pela rede. Entre pelo endereço https da sua instância. "
              "Se você usa um proxy que não envia o cabeçalho X-Forwarded-Proto, "
              "suba o app com CEQ_PERMITE_HTTP=1 no .env.")


def _bloqueio_global() -> int:
    """Segundos até o teto geral de falhas liberar, ou 0. Chamar com LOGIN_LOCK."""
    agora = time.time()
    while LOGIN_FALHAS_GLOBAIS and LOGIN_FALHAS_GLOBAIS[0] <= agora - LOGIN_GLOBAL_JANELA:
        LOGIN_FALHAS_GLOBAIS.pop(0)
    if len(LOGIN_FALHAS_GLOBAIS) < LOGIN_GLOBAL_LIMITE:
        return 0
    # libera quando a falha mais antiga que conta pro teto sair da janela
    saida = LOGIN_FALHAS_GLOBAIS[-LOGIN_GLOBAL_LIMITE] + LOGIN_GLOBAL_JANELA
    return max(1, int(saida - agora) + 1)


def login_bloqueado(ip: str) -> int:
    """Segundos restantes de bloqueio (do IP ou do teto geral), ou 0 se pode tentar."""
    with LOGIN_LOCK:
        falhas, ate = LOGIN_TENTATIVAS.get(ip, (0, 0.0))
        restante = ate - time.time()
        do_ip = int(restante) + 1 if restante > 0 else 0
        return max(do_ip, _bloqueio_global())


def registra_falha(ip: str) -> None:
    with LOGIN_LOCK:
        agora = time.time()
        if len(LOGIN_TENTATIVAS) >= LOGIN_IPS_MAX:
            # só sai quem já cumpriu o bloqueio há mais de uma espera máxima
            for velho in [k for k, (_, ate) in LOGIN_TENTATIVAS.items()
                          if ate < agora - LOGIN_ESPERA_MAX]:
                LOGIN_TENTATIVAS.pop(velho, None)
            if len(LOGIN_TENTATIVAS) >= LOGIN_IPS_MAX:
                LOGIN_TENTATIVAS.clear()   # o teto geral segue valendo
        falhas, _ = LOGIN_TENTATIVAS.get(ip, (0, 0.0))
        falhas += 1
        espera = 0.0
        if falhas >= LOGIN_LIMITE:
            espera = min(LOGIN_ESPERA_BASE * (2 ** (falhas - LOGIN_LIMITE)), LOGIN_ESPERA_MAX)
        LOGIN_TENTATIVAS[ip] = (falhas, agora + espera)
        LOGIN_FALHAS_GLOBAIS.append(agora)
        geral = _bloqueio_global()
    db.log_event("login_falhou", payload={"ip": ip, "falhas": falhas,
                                          "bloqueado_por_s": int(max(espera, geral))})


def limpa_falhas(ip: str) -> None:
    with LOGIN_LOCK:
        LOGIN_TENTATIVAS.pop(ip, None)


def _iguais(a: str, b: str) -> bool:
    """Comparação em tempo constante. Em bytes porque hmac.compare_digest recusa
    str com acento (TypeError): senha com "ç" derrubava o login com erro 500."""
    return hmac.compare_digest((a or "").encode("utf-8"), (b or "").encode("utf-8"))


# ---------- token fora do log ----------
#
# O link do primeiro acesso é /instalar?t=<token>. O log de acesso do uvicorn grava a
# URL inteira, então o token ia parar no `docker logs` de quem pedisse ajuda colando
# o log. O filtro troca o valor por *** antes de o registro sair. O POST manda o
# token no corpo, mas o GET do link continua na URL.

_RE_TOKEN_URL = re.compile(r"([?&]t=)[^&\s\"']*")


class FiltroTokenSetup(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            record.args = tuple(_RE_TOKEN_URL.sub(r"\1***", a) if isinstance(a, str) else a
                                for a in record.args)
        if isinstance(record.msg, str):
            record.msg = _RE_TOKEN_URL.sub(r"\1***", record.msg)
        return True


FILTRO_TOKEN_SETUP = FiltroTokenSetup()


def instalar_filtro_log() -> None:
    lg = logging.getLogger("uvicorn.access")
    if FILTRO_TOKEN_SETUP not in lg.filters:
        lg.addFilter(FILTRO_TOKEN_SETUP)


# ---------- ciclo de vida ----------

async def startup():
    instalar_filtro_log()
    db.init()
    runtime.carregar_config()
    if not meta_app_secret():
        print("[ceq] ATENCAO: chave secreta do app da Meta vazia (nem no .env, nem em "
              "/config). O /webhook vai recusar os eventos da Meta (503) ate voce "
              "preencher: sem o secret nao ha como provar que o evento veio mesmo da Meta.",
              flush=True)
    asyncio.get_event_loop().run_in_executor(None, check_license)
    asyncio.create_task(_token_refresh_loop())
    asyncio.create_task(_retencao_loop())
    # thread daemon: é ela que faz os delays vencerem e os timeouts caírem no ramo
    # certo. Sem ela, fluxo com delay para no meio e nunca continua.
    threading.Thread(target=runtime.worker_loop, daemon=True, name="ceq-worker").start()
    asyncio.get_event_loop().run_in_executor(None, _resubscrever_webhooks)
    asyncio.get_event_loop().run_in_executor(None, _atualizar_fotos)
    asyncio.get_event_loop().run_in_executor(None, _atualizar_estado_wa)


def _baixar_avatar(account_id, access_token) -> bool:
    """Baixa o JPEG da foto de perfil pro volume de dados e aponta o painel pra ele.

    A URL do CDN do Instagram vem assinada com prazo de validade: guardar o link
    (como era até a v1.6.3) obriga a renovar pra sempre. Guardando a imagem em si,
    o painel serve de /avatar/<id> e nada mais vence. A troca do arquivo é por
    rename — nunca fica avatar pela metade — e falha de rede não apaga a cópia
    que já funciona.
    """
    url = instagram.fetch_own_pic(access_token)
    dados = instagram.download_pic(url) if url else b""
    if not dados:
        return False
    destino = db.DATA_DIR / f"avatar_{account_id}.jpg"
    tmp = destino.with_suffix(".tmp")
    tmp.write_bytes(dados)
    tmp.replace(destino)
    db.update_account_pic(account_id, f"/avatar/{account_id}")
    return True


def _atualizar_fotos():
    """Re-baixa a foto de cada conta no boot e a cada ciclo do refresh de token,
    pra acompanhar troca de foto no Instagram. Se a Meta não responder, a cópia
    local continua servindo."""
    for account in db.all_accounts():
        try:
            _baixar_avatar(account["id"], account["access_token"])
        except Exception as e:
            db.log_event("foto_perfil", account["id"], ok=False,
                         payload={"erro": instagram.sem_segredo(e)[:200]})


def _resubscrever_webhooks():
    """Reassina os campos de webhook em toda conta já conectada.

    A assinatura só acontecia no /auth/callback. Quem já tinha conectado antes desta
    versão ficaria sem live_comments e sem messaging_postbacks, ou seja, comentário
    em live e clique de botão simplesmente não chegariam — sem erro nenhum, só
    silêncio. A chamada é idempotente na Meta, então repetir no boot não custa nada.
    """
    for account in db.all_accounts():
        try:
            ok, detalhe = instagram.subscribe_webhooks(account["access_token"])
            db.log_event("subscribe_webhooks", account["id"], ok=ok,
                         payload={"detalhe": detalhe[:300]})
        except Exception as e:
            db.log_event("subscribe_webhooks", account["id"], ok=False,
                         payload={"erro": instagram.sem_segredo(e)[:300]})


async def _retencao_loop():
    """Aplica a retenção de dados uma vez por dia.

    RETENCAO_LEADS_DIAS apaga lead parado há mais tempo que isso, junto com as tags e
    os campos dele (telefone, e-mail). RETENCAO_EVENTOS_DIAS limpa o log técnico.
    Vazio ou 0 desliga, que é o padrão: ninguém perde dado por atualizar o app sem
    saber. Quem liga, cumpre a política de privacidade em vez de só publicá-la.
    """
    while True:
        try:
            leads = db.purgar_leads_antigos(RETENCAO_LEADS_DIAS)
            eventos = db.purgar_eventos_antigos(RETENCAO_EVENTOS_DIAS)
            db.limpar_sessoes_vencidas()
            if leads or eventos:
                db.log_event("retencao", payload={"leads_apagados": leads,
                                                  "eventos_apagados": eventos})
        except Exception as e:
            db.log_event("retencao", ok=False, payload={"erro": instagram.sem_segredo(e)[:200]})
        await asyncio.sleep(24 * 3600)


async def _token_refresh_loop():
    """Renova tokens diariamente quando faltar <50 dias (efetivamente ~semanal)."""
    while True:
        await asyncio.sleep(6 * 3600)
        await asyncio.get_event_loop().run_in_executor(None, check_license)
        await asyncio.get_event_loop().run_in_executor(None, _atualizar_fotos)
        await asyncio.get_event_loop().run_in_executor(None, _atualizar_estado_wa)
        for account in db.all_accounts():
            try:
                if 0 < instagram.token_days_left(account) < 50:
                    ok, detail = instagram.refresh_token(account)
                    db.log_event("token_refresh", account["id"], ok=ok, payload={"detail": detail})
            except Exception as e:  # nunca derrubar o loop
                db.log_event("token_refresh", account["id"], ok=False,
                             payload={"erro": instagram.sem_segredo(e)[:300]})


# ---------- público ----------

@app.get("/health")
def health(request: Request):
    """Público responde só se o app está de pé. O detalhe (qual conta, quantos dias
    de token, qual membro do Club) só sai pra quem está logado: é informação de dono,
    e antes qualquer um com a URL conseguia ler."""
    account = db.first_account()
    basico = {"ok": True, "conta_conectada": bool(account)}
    if not logged_in(request):
        return basico
    return {
        **basico,
        "versao": VERSAO,
        "username": account and account.get("username"),
        "token_dias_restantes": account and round(instagram.token_days_left(account), 1),
        "fluxos_ativos": len(db.list_flows(only_active=True)),
        "ativacao": LICENSE["status"],
        "membro": LICENSE["member"],
        # saúde do rate limit: quanto a instância mandou na última hora, o teto
        # local, e se a Meta mandou esperar (0 = livre)
        "envios_ultima_hora": db.envios_na_ultima_hora(account["id"]) if account else 0,
        "teto_envios_hora": runtime.teto_atual(),
        "cooldown_meta_s": int(instagram.cooldown_restante()),
    }


@app.get("/webhook")
def webhook_verify(request: Request):
    """Verificação da URL pelo painel da Meta. Continua funcionando sem APP_SECRET:
    é justamente o passo que o dono faz ANTES de ter o secret em mãos."""
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and _iguais(
            q.get("hub.verify_token", ""), VERIFY_TOKEN):
        return PlainTextResponse(q.get("hub.challenge", ""))
    return PlainTextResponse("token invalido", status_code=403)


@app.post("/webhook")
async def webhook_receive(request: Request, background: BackgroundTasks):
    raw = await request.body()

    # Sem APP_SECRET não existe como provar que o evento veio da Meta. Antes isso
    # simplesmente pulava a conferência, ou seja, a rota aceitava POST de qualquer
    # um: bastava forjar o payload pra fazer a instância mandar DM em nome do dono.
    # Agora recusa. A porta fecha, e o painel avisa o que falta configurar.
    # Cada produto com a sua chave, escolhida pelo `object` do corpo: a do Instagram
    # não pode assinar evento do WhatsApp nem o contrário. O WhatsApp usa a chave do
    # app geral; a do Instagram só vale pra ele se a do WA não foi preenchida (app
    # em que as duas são a mesma).
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None
    objeto = payload.get("object") if isinstance(payload, dict) else ""
    if objeto == "whatsapp_business_account":
        segredo, falta = meta_wa_app_secret() or meta_app_secret(), "META_WA_APP_SECRET vazio"
    else:
        segredo, falta = meta_app_secret(), "META_APP_SECRET vazio"
    if not segredo:
        db.log_event("webhook_recusado", payload={"motivo": falta})
        return Response(status_code=503)

    sig = request.headers.get("X-Hub-Signature-256", "")
    if not _iguais(sig, "sha256=" + hmac.new(segredo.encode(), raw, hashlib.sha256).hexdigest()):
        return Response(status_code=403)
    if payload is None:
        return Response(status_code=200)
    db.log_event("webhook", payload={"resumo": _resumo_webhook(payload)})
    background.add_task(flowengine.process_payload, payload)
    return Response(status_code=200)


def _resumo_webhook(payload):
    kinds = []
    for entry in payload.get("entry", []):
        for ev in entry.get("messaging", []):
            kinds.append("message" if ev.get("message") else next(
                (k for k in ("read", "reaction", "message_edit") if k in ev), "outro"))
        for ch in entry.get("changes", []):
            if payload.get("object") == "whatsapp_business_account":
                valor = ch.get("value") or {}
                kinds += ["wa_message"] * len(valor.get("messages") or [])
                kinds += ["wa_status"] * len(valor.get("statuses") or [])
                if not (valor.get("messages") or valor.get("statuses")):
                    kinds.append("wa_" + ch.get("field", "outro"))
                continue
            kinds.append(ch.get("field", "outro"))
    return kinds


# Conectar a conta do Instagram é ação de dono. As duas rotas eram públicas: com o
# app da Meta em modo Live, qualquer pessoa autorizava a PRÓPRIA conta e ela entrava
# no banco (numa instância recém-instalada, virava a conta principal). Agora exigem
# a sessão do painel, e o `state` amarra a volta da Meta ao navegador que começou.

OAUTH_STATE_COOKIE = "ceq_oauth_state"


@app.get("/auth/start")
def auth_start(request: Request):
    if (r := require_login(request)):
        return r
    app_id = meta_app_id()
    if not (app_id and BASE_URL):
        return PlainTextResponse("Preencha o ID do app do Instagram em Configurações (ou "
                                 "META_APP_ID no .env) e o BASE_URL primeiro.", status_code=500)
    state = secrets.token_urlsafe(24)
    resp = RedirectResponse(
        instagram.authorize_url(app_id, f"{BASE_URL}/auth/callback", state))
    # Lax: o cookie volta no redirecionamento de topo que a Meta faz pro callback
    resp.set_cookie(OAUTH_STATE_COOKIE, state, httponly=True, max_age=600,
                    samesite="lax", secure=COOKIE_SEGURO)
    return resp


@app.get("/auth/callback")
def auth_callback(request: Request, code: str = "", state: str = "", error: str = "",
                  error_description: str = ""):
    if (r := require_login(request)):
        return r
    esperado = request.cookies.get(OAUTH_STATE_COOKIE, "")
    if not esperado or not _iguais(state, esperado):
        return PlainTextResponse(
            "Esta conexão não começou neste navegador. Volte ao painel e clique em "
            "Conectar Instagram de novo.", status_code=400)
    if error:
        db.log_event("oauth_erro", payload={"error": error[:100],
                                            "desc": error_description[:300]})
        return PlainTextResponse(f"Erro no OAuth: {error[:100]} — {error_description[:300]}",
                                 status_code=400)
    try:
        info = instagram.exchange_code(meta_app_id(), meta_app_secret(),
                                      f"{BASE_URL}/auth/callback", code)
    except Exception as e:
        # o detalhe vai só pro log, e já sem segredo: a exceção do requests carrega a
        # URL inteira, com client_secret e access_token na query
        db.log_event("oauth_erro", payload={"erro": instagram.sem_segredo(e)[:300]})
        return PlainTextResponse(
            "Falha ao conectar com a Meta. O detalhe está no histórico de eventos do "
            "painel (oauth_erro). Tente de novo em instantes.", status_code=502)

    account = db.upsert_account(info["ig_id"], info["ig_user_id"], info["username"],
                                info["access_token"], info["token_expires_at"])
    try:
        _baixar_avatar(account["id"], info["access_token"])
    except Exception as e:
        db.log_event("foto_perfil", account["id"], ok=False, payload={"erro": instagram.sem_segredo(e)[:200]})
    sub_ok, sub_body = instagram.subscribe_webhooks(info["access_token"])
    db.log_event("oauth_ok", account["id"], who=info["username"],
                 payload={"permissions": info["permissions"], "webhook_sub": sub_ok})
    resp = RedirectResponse("/painel?conectado=1", status_code=303)
    resp.delete_cookie(OAUTH_STATE_COOKIE)
    return resp


@app.get("/privacy")
def privacy(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {
        "retencao_dias": RETENCAO_LEADS_DIAS,
        "retencao_eventos_dias": RETENCAO_EVENTOS_DIAS,
    })


# ---------- painel ----------

@app.get("/")
def index():
    return RedirectResponse("/painel", status_code=303)


@app.get("/login")
def login_page(request: Request, proximo: str = ""):
    # avisa antes de a pessoa digitar, não depois de mandar a senha
    return templates.TemplateResponse(request, "login.html", {
        "erro": AVISO_HTTP if conexao_insegura(request) else "",
        "proximo": mcp_server.proximo_seguro(proximo) if proximo else ""})


@app.post("/login")
def login_post(request: Request, senha: str = Form(""), proximo: str = Form("")):
    if conexao_insegura(request):
        db.log_event("login_por_http", payload={"ip": _ip_de(request),
                                                "host": request.url.hostname})
        return templates.TemplateResponse(request, "login.html", {"erro": AVISO_HTTP,
                                          "proximo": proximo}, status_code=400)
    ip = _ip_de(request)
    espera = login_bloqueado(ip)
    if espera:
        minutos = max(1, round(espera / 60))
        return templates.TemplateResponse(request, "login.html", {
            "erro": f"Tentativas demais. Tente de novo em {minutos} min.",
            "proximo": mcp_server.proximo_seguro(proximo) if proximo else ""}, status_code=429)

    if conferir_senha(senha):
        limpa_falhas(ip)
        # `proximo` só pode ser a tela de "permitir acesso" do Claude (ver mcp_server)
        resp = RedirectResponse(mcp_server.proximo_seguro(proximo), status_code=303)
        resp.set_cookie("ceq_session", db.criar_sessao(ip), httponly=True,
                        max_age=30 * 86400, samesite="lax", secure=COOKIE_SEGURO)
        return resp

    registra_falha(ip)
    return templates.TemplateResponse(request, "login.html", {
        "erro": "Senha incorreta.",
        "proximo": mcp_server.proximo_seguro(proximo) if proximo else ""}, status_code=401)


# ---------- primeiro acesso ----------
#
# Instalação nova (pelo chão) não traz ADMIN_PASSWORD no .env: o instalador gera um
# CEQ_SETUP_TOKEN e entrega ao dono o link /instalar?t=<token>. A página só existe
# enquanto não há senha nenhuma; depois de criada, vira 404 pra sempre. Sem o token
# certo também é 404, pra não anunciar que a instância está esperando dono.


def _instalar_aberto(t: str) -> bool:
    return bool(SETUP_TOKEN) and not senha_definida() and _iguais(t, SETUP_TOKEN)


@app.get("/instalar", response_class=HTMLResponse)
def instalar_page(request: Request, t: str = ""):
    if not _instalar_aberto(t):
        raise HTTPException(404)
    return templates.TemplateResponse(request, "instalar.html", {"t": t, "erro": ""})


@app.post("/instalar", response_class=HTMLResponse)
def instalar_post(request: Request, t: str = Form(""), senha: str = Form(""),
                  senha2: str = Form("")):
    # o token vem no corpo (fora do log de acesso); a query fica de reserva pra não
    # quebrar formulário antigo aberto numa aba
    t = t or request.query_params.get("t", "")
    if not _instalar_aberto(t):
        raise HTTPException(404)
    if len(senha) < 8:
        return templates.TemplateResponse(request, "instalar.html", {
            "t": t, "erro": "A senha precisa ter pelo menos 8 caracteres."})
    if senha != senha2:
        return templates.TemplateResponse(request, "instalar.html", {
            "t": t, "erro": "As senhas não batem."})
    definir_senha(senha)
    db.log_event("senha_definida", payload={"origem": "instalar"})
    return RedirectResponse("/login", status_code=303)


@app.get("/logout")
def logout(request: Request):
    db.apagar_sessao(request.cookies.get("ceq_session", ""))
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("ceq_session")
    return resp


@app.post("/logout-todos")
def logout_todos(request: Request):
    """Derruba todas as sessões abertas, inclusive a de outro dispositivo. É o botão
    de pânico de quem acha que a senha vazou (trocar a senha no .env não bastava:
    o cookie antigo continuava valendo)."""
    guard = require_login(request)
    if guard:
        return guard
    n = db.apagar_todas_sessoes()
    db.log_event("sessoes_revogadas", payload={"quantidade": n})
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("ceq_session")
    return resp


NOMES_GATILHO = {
    "comment": "comentário em post ou Reel",
    "live_comment": "comentário durante a live",
    "story_reply": "resposta de story",
    "dm": "mensagem no direct",
    "wa_message": "mensagem no WhatsApp",
    "wa_template_reply": "clique em botão de template do WhatsApp",
}


def _quando(ts: str) -> str:
    """'2026-07-21T18:43:51Z' -> 'hoje 18:43' / 'ontem 09:12' / '18/jul'."""
    if not ts:
        return ""
    import datetime as _dt
    try:
        q = _dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return ts[:10]
    dias = (_dt.datetime.now(_dt.timezone.utc).date() - q.date()).days
    if dias == 0:
        return f"hoje {q:%H:%M}"
    if dias == 1:
        return f"ontem {q:%H:%M}"
    if dias < 7:
        return f"há {dias} dias"
    meses = ["jan", "fev", "mar", "abr", "mai", "jun",
             "jul", "ago", "set", "out", "nov", "dez"]
    return f"{q.day}/{meses[q.month - 1]}"


templates.env.filters["quando"] = _quando


@app.get("/regras")
def regras_saiu():
    """A tela de regras foi substituída pelos fluxos. Quem tiver o endereço salvo
    cai na lista em vez de tomar um 404."""
    return RedirectResponse("/fluxos", status_code=308)


@app.get("/fluxos")
def fluxos_page(request: Request):
    """Lista dos fluxos. É por aqui que se entra, não direto no canvas: quem abre o
    menu quer ver o que existe e como está indo, não cair numa tela de edição."""
    guard = require_login(request)
    if guard:
        return guard
    account = db.first_account()
    fluxos = []
    if account:
        stats = db.flow_stats(account["id"])
        for f in db.list_flows(account["id"]):
            s = stats.get(f["name"], {})
            gatilhos = []
            for t in db.list_triggers(f["id"]):
                gatilhos.append({**t, "nome": NOMES_GATILHO.get(t["type"], t["type"])})
            fluxos.append({
                "id": f["id"], "name": f["name"], "active": f["active"],
                "passos": len(f["graph"].get("nodes", [])),
                "triggers": gatilhos,
                "entregas": s.get("entregas", 0),
                "ultimo": _quando(s.get("ultimo", "")),
            })
    return templates.TemplateResponse(request, "fluxos.html", {
        "account": account, "fluxos": fluxos,
    })


@app.get("/editor")
def editor(request: Request):
    """Canvas de fluxo. Se o build do editor não existir (instalação que rodou só o
    backend), avisa em vez de dar 404 seco."""
    guard = require_login(request)
    if guard:
        return guard
    if not EDITOR_INDEX.exists():
        return HTMLResponse(
            "<p style='font-family:sans-serif;padding:2rem'>O editor não foi compilado "
            "nesta instalação. Rode <code>npm ci && npx vite build</code> dentro de "
            "<code>editor/</code>, ou use a imagem Docker oficial.</p>", status_code=200)
    return FileResponse(EDITOR_INDEX)


@app.get("/avatar/{account_id}")
def avatar(request: Request, account_id: int):
    """Cópia local da foto de perfil, atrás do login como o resto do painel."""
    guard = require_login(request)
    if guard:
        return guard
    arq = db.DATA_DIR / f"avatar_{account_id}.jpg"
    if not arq.exists():
        return PlainTextResponse("sem foto", status_code=404)
    return FileResponse(arq, media_type="image/jpeg")


@app.get("/painel")
def painel(request: Request):
    guard = require_login(request)
    if guard:
        return guard
    account = db.first_account()
    app_id, app_secret = meta_app_id(), meta_app_secret()
    return templates.TemplateResponse(request, "painel.html", {
        "account": account,
        "token_dias": account and round(instagram.token_days_left(account)),
        "stats": db.stats(),
        "leads_info": db.leads_by_who(account["id"]) if account else {},
        "leads_total": db.leads_count(account["id"]) if account else 0,
        "conectado": request.query_params.get("conectado"),
        "configurado": bool(app_id and app_secret and BASE_URL),
        "falta_secret": not app_secret,
        "faltando": [nome for nome, valor in (("META_APP_ID", app_id),
                                              ("META_APP_SECRET", app_secret),
                                              ("BASE_URL", BASE_URL)) if not valor],
        "licenca": LICENSE,
        # -3h: o ts é UTC, e às 21h de Brasília "hoje" em UTC já é amanhã
        "hist_desde": db.in_seconds_iso(-30 * 86400 - 10800)[:10],
        "hist_ate": db.in_seconds_iso(-10800)[:10],
        "wa": wa_estado(account),
    })


# ---------- configurações ----------
#
# O que é operação (teto de envio, alerta) mora em `ajustes` e muda ao vivo por
# aqui. O ID e a chave secreta do app da Meta também podem entrar por aqui (cifrados
# com CEQ_ENCRYPTION_KEY), porque na instalação pelo chão o dono não edita .env; se
# estiverem no .env, o .env manda e o formulário fica travado. O resto do bootstrap
# (BASE_URL, CLUB_TOKEN) continua no .env e a aba só mostra o status.


def _status_env():
    """Linhas da tabela somente leitura: (nome, valor exibível, preenchido?).
    Segredo nunca aparece, nem mascarado: só 'preenchido' ou 'faltando'."""
    app_id, app_secret = meta_app_id(), meta_app_secret()
    return [
        ("META_APP_ID", app_id or "faltando", bool(app_id)),
        ("META_APP_SECRET", "preenchido" if app_secret else "faltando", bool(app_secret)),
        ("BASE_URL", BASE_URL or "faltando", bool(BASE_URL)),
        ("CEQ_ENCRYPTION_KEY", {"ok": "preenchida", "ausente": "faltando",
                                "invalida": "chave inválida"}[segredos.estado_chave()],
         segredos.cifrado_disponivel()),
        ("ADMIN_PASSWORD", "preenchido" if ADMIN_PASSWORD else
         ("definida no primeiro acesso" if senha_definida() else "faltando"), senha_definida()),
        ("CLUB_TOKEN", LICENSE["status"], LICENSE["status"] == "ativada"),
        ("RETENCAO_LEADS_DIAS", str(RETENCAO_LEADS_DIAS) if RETENCAO_LEADS_DIAS else "desligada",
         True),
        ("RETENCAO_EVENTOS_DIAS", str(RETENCAO_EVENTOS_DIAS) if RETENCAO_EVENTOS_DIAS else "desligada",
         True),
    ] + ([("META_WA_APP_SECRET",
           "preenchido" if meta_wa_app_secret() else "faltando (usa a do Instagram)",
           bool(meta_wa_app_secret()))]
         if whatsapp.configurado(db.first_account()) else [])


@app.get("/config")
def config_page(request: Request):
    return _config(request)


def _config(request: Request, extra: dict | None = None):
    guard = require_login(request)
    if guard:
        return guard
    account = db.first_account()
    token, chat = alerta.credenciais()
    return templates.TemplateResponse(request, "config.html", {
        **mcp_contexto(), **(extra or {}),
        "account": account,
        "teto": runtime.teto_atual(),
        "teto_maximo": runtime.TETO_MAXIMO,
        "envios_hora": db.envios_na_ultima_hora(account["id"]) if account else 0,
        "cooldown_s": int(instagram.cooldown_restante()),
        "alerta_ativo": bool(token and chat),
        "alerta_token_dica": f"termina em {token[-4:]}" if token else "",
        "alerta_chat": chat,
        "env_status": _status_env(),
        "meta_app_id": meta_app_id(),
        "tem_secret": bool(meta_app_secret()),
        "cifrado": segredos.cifrado_disponivel(),
        "estado_chave": segredos.estado_chave(),
        "id_no_env": bool(os.environ.get("META_APP_ID")),
        "so_env": bool(os.environ.get("META_APP_SECRET")),
        "base_url": BASE_URL,
        "verify_token": VERIFY_TOKEN,
        "salvo": request.query_params.get("salvo"),
        "teste": request.query_params.get("teste"),
        "wa": wa_estado(account),
        "wa_ids": {"waba": (account or {}).get("wa_waba_id") or "",
                   "phone": (account or {}).get("wa_phone_number_id") or ""},
        "tem_wa_token": bool(account and whatsapp.token(account)),
        "tem_wa_secret": bool(meta_wa_app_secret()),
        "wa_secret_no_env": bool(os.environ.get("META_WA_APP_SECRET")),
        "wa_teto": int(runtime.LIMITER_WA.capacidade),
        "wa_teto_maximo": runtime.WA_TETO_MAXIMO,
        "wa_limite_diario": db.get_ajuste("wa_limite_diario"),
        "wa_aviso": request.query_params.get("wa"),
        "mcp_aviso": request.query_params.get("mcp"),
    })


@app.post("/config")
def config_save(request: Request, teto: str = Form(""), alerta_token: str = Form(""),
                alerta_chat: str = Form(""), desativar_alerta: str = Form(""),
                meta_app_id: str = Form(""), meta_app_secret: str = Form(""),
                wa_waba_id: str = Form(""), wa_phone_number_id: str = Form(""),
                wa_token: str = Form(""), meta_wa_app_secret: str = Form(""),
                wa_envios_hora: str = Form(""), wa_limite_diario: str = Form(""),
                wa_limite_diario_no_form: str = Form(""), wa_desconectar: str = Form("")):
    guard = require_login(request)
    if guard:
        return guard
    mudou = []
    destino = "/config?salvo=1"

    # campo em branco preserva o valor atual (a chave secreta nunca volta pro
    # formulário). Com o par no .env, o .env manda e o formulário nem mostra o campo.
    if meta_app_id.strip():
        segredos.guardar("meta_app_id", meta_app_id.strip())
        mudou.append("meta_app_id")
    if meta_app_secret.strip():
        segredos.guardar("meta_app_secret", meta_app_secret.strip())
        mudou.append("meta_app_secret")

    if teto.strip().isdigit():
        efetivo = runtime.aplicar_teto(int(teto.strip()))
        db.set_ajuste("teto_envios_hora", efetivo)
        mudou.append("teto")

    if desativar_alerta:
        # "off" e não vazio de propósito: vazio faria o .env religar no restart
        db.set_ajuste("alerta_telegram_token", "off")
        db.set_ajuste("alerta_telegram_chat", "")
        mudou.append("alerta_off")
    else:
        # campo em branco preserva o valor atual: o formulário nunca mostra o
        # token salvo, então reenviar a página não pode apagá-lo
        if alerta_token.strip():
            db.set_ajuste("alerta_telegram_token", alerta_token.strip())
            mudou.append("alerta_token")
        if alerta_chat.strip():
            db.set_ajuste("alerta_telegram_chat", alerta_chat.strip())
            mudou.append("alerta_chat")

    if meta_wa_app_secret.strip():
        segredos.guardar("meta_wa_app_secret", meta_wa_app_secret.strip())
        mudou.append("meta_wa_app_secret")
    if wa_envios_hora.strip().isdigit():
        db.set_ajuste("wa_envios_hora", runtime.aplicar_teto_wa(int(wa_envios_hora.strip())))
        mudou.append("wa_envios_hora")
    # o painel diz "vazio = o limite do número na Meta": campo em branco apaga o
    # ajuste. Só quando o campo estava na página (marcador escondido ao lado dele): o
    # FastAPI entrega ausente e vazio iguais, e POST sem o campo não pode apagar.
    limite_txt = wa_limite_diario.strip()
    if limite_txt.isdigit():
        db.set_ajuste("wa_limite_diario", int(limite_txt))
        mudou.append("wa_limite_diario")
    elif not limite_txt and wa_limite_diario_no_form and db.get_ajuste("wa_limite_diario"):
        db.set_ajuste("wa_limite_diario", "")
        mudou.append("wa_limite_diario")

    campos_wa = [c for c in (wa_waba_id, wa_phone_number_id, wa_token) if c.strip()]
    if campos_wa or wa_desconectar:
        account = db.first_account()
        if not account:
            # o número mora na conta do Instagram: sem ela, não há onde ligar
            destino = "/config?wa=sem_conta"
        elif wa_desconectar:
            db.set_wa_config(account["id"], "", "")
            segredos.guardar(whatsapp.chave_token(account["id"]), "")
            mudou.append("wa_desconectado")
        else:
            db.set_wa_config(account["id"], wa_waba_id.strip() or account.get("wa_waba_id") or "",
                             wa_phone_number_id.strip() or account.get("wa_phone_number_id") or "")
            if wa_token.strip():
                segredos.guardar(whatsapp.chave_token(account["id"]), wa_token.strip())
            mudou += [nome for nome, v in (("wa_waba_id", wa_waba_id),
                                           ("wa_phone_number_id", wa_phone_number_id),
                                           ("wa_token", wa_token)) if v.strip()]
            account = db.get_account(account["id"])
            info = whatsapp.fetch_phone_info(account)
            if info:
                db.update_wa_estado(account["id"], info["numero"], info["nome"],
                                    info["qualidade"], info["limite"])
            sub_ok, _ = whatsapp.subscribe_app(account)
            # só se deu certo: nem ID nem token entram no log
            db.log_event("wa_conectado", account["id"], ok=bool(info) and sub_ok,
                         payload={"estado": bool(info), "webhook": sub_ok})

    # o log diz O QUE mudou, nunca o valor: token não entra em log de evento
    db.log_event("config_alterada", payload={"campos": mudou})
    return RedirectResponse(destino, status_code=303)


# ---------- conectar ao Claude (MCP) ----------

def mcp_contexto() -> dict:
    """Seção "Conectar ao Claude" de /config. Nunca leva token: do manual só os 4
    últimos caracteres, das conexões OAuth o nome do cliente e o último uso."""
    tokens = db.mcp_tokens_ativos()
    manual = next((t for t in tokens if t["tipo"] == "manual"), None)
    conexoes = {}
    for t in tokens:
        if t["tipo"] == "manual":
            continue
        c = conexoes.setdefault(t["cliente_id"], {"cliente_id": t["cliente_id"],
                                                  "nome": t["cliente_nome"] or "Cliente MCP",
                                                  "ultimo_uso": "", "desde": t["criado_em"]})
        c["ultimo_uso"] = max(c["ultimo_uso"], t["ultimo_uso"] or "")
        c["desde"] = min(c["desde"], t["criado_em"])
    base = BASE_URL or "https://SEU-DOMINIO"
    return {"mcp_url": base + "/mcp", "mcp_manual": manual,
            "mcp_conexoes": sorted(conexoes.values(), key=lambda c: c["desde"]),
            "mcp_https": BASE_URL.startswith("https://")}


@app.post("/config/mcp/token")
def config_mcp_token(request: Request):
    """Gera (ou troca) o token manual. Ele aparece uma vez, nesta resposta, e só o
    hash fica no banco; não vai pra URL nem pra redirecionamento."""
    guard = require_login(request)
    if guard:
        return guard
    db.mcp_apagar_tokens(["manual"])
    novo = "ceq_" + secrets.token_urlsafe(32)
    db.mcp_guardar_token(novo, "manual", cliente_nome="token manual")
    db.log_event("mcp_token_gerado")
    return _config(request, {"mcp_token_novo": novo})


@app.post("/config/mcp/revogar")
def config_mcp_revogar(request: Request, cliente_id: str = Form("")):
    guard = require_login(request)
    if guard:
        return guard
    if cliente_id:
        db.mcp_apagar_do_cliente(cliente_id)
    else:
        db.mcp_apagar_tokens(["manual"])
    db.log_event("mcp_acesso_revogado", payload={"conexao": "oauth" if cliente_id else "manual"})
    return RedirectResponse("/config?mcp=revogado#mcp", status_code=303)


@app.post("/config/teste-alerta")
def config_teste_alerta(request: Request):
    guard = require_login(request)
    if guard:
        return guard
    ok = alerta.avisar("Teste de alerta do comenta EU QUERO: se você leu isso, "
                       "o vigia de rate limit sabe onde te encontrar.", sincrono=True)
    return RedirectResponse(f"/config?teste={'ok' if ok else 'falhou'}", status_code=303)


@app.get("/leads")
def leads(request: Request, keyword: str = "", segue: str = "", busca: str = "",
          ordem: str = "recente"):
    guard = require_login(request)
    if guard:
        return guard
    account = db.first_account()
    if not account:
        return templates.TemplateResponse(request, "leads.html", {
            "account": None, "leads": [], "resumo": {"total": 0, "seguidores": 0,
                                                     "palavras": []},
            "filtros": {}, "ordem": ordem,
        })
    segue_num = 1 if segue == "1" else (0 if segue == "0" else None)
    lista = db.list_leads(account["id"], limit=500, keyword=keyword or None,
                          segue=segue_num, busca=busca or None, ordem=ordem)
    return templates.TemplateResponse(request, "leads.html", {
        "account": account,
        "leads": lista,
        "resumo": db.leads_resumo(account["id"]),
        "filtros": {"keyword": keyword, "segue": segue, "busca": busca},
        "ordem": ordem,
        "retencao_dias": RETENCAO_LEADS_DIAS,
    })


@app.post("/leads/{lead_id}/apagar")
def apagar_lead(request: Request, lead_id: int):
    """Exclusão a pedido da pessoa. Some o lead e tudo que pende dele: tags, campos
    capturados (telefone, e-mail) e sessões de fluxo. Sem isso a política de
    privacidade prometia uma exclusão que o app não sabia fazer."""
    guard = require_login(request)
    if guard:
        return guard
    if db.apagar_lead(lead_id):
        db.log_event("lead_apagado", payload={"lead_id": lead_id})
    return RedirectResponse("/leads", status_code=303)


# ---------- WhatsApp: templates ----------

@app.get("/templates")
def templates_wa_page(request: Request):
    guard = require_login(request)
    if guard:
        return guard
    account = db.first_account()
    ativo = whatsapp.configurado(account)
    lista, pastas = [], []
    if ativo:
        api.sincronizar_se_pendente(account)  # quem acabou de ser aprovado já aparece
        lista = [api._template_publico(t) for t in db.listar_templates(account["id"])]
        pastas = db.listar_pastas(account["id"])
    return templates.TemplateResponse(request, "templates_wa.html", {
        "account": account, "wa_configurado": ativo, "templates_wa": lista, "pastas": pastas})


# ---------- WhatsApp: transmissões ----------

import datetime as _dt  # noqa: E402

RITMO_MIN, RITMO_MAX = 1, 80


def _brasilia_para_utc(valor: str) -> str:
    """'2026-10-22T09:30' digitado em Brasília -> ISO UTC. Brasil sem horário de
    verão desde 2019: é sempre -3h."""
    try:
        local = _dt.datetime.strptime(valor[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return ""
    return (local + _dt.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_para_brasilia(valor: str) -> str:
    try:
        utc = _dt.datetime.strptime(valor, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return ""
    return (utc - _dt.timedelta(hours=3)).strftime("%d/%m %H:%M")


templates.env.filters["brasilia"] = _utc_para_brasilia


def _sem_wa(request: Request):
    return templates.TemplateResponse(request, "transmissoes.html", {
        "account": db.first_account(), "wa_configurado": False, "transmissoes": [],
        "erro": "Ligue um número de WhatsApp em Configurações antes de criar transmissões."},
        status_code=400)


@app.get("/transmissoes")
def transmissoes_page(request: Request):
    guard = require_login(request)
    if guard:
        return guard
    from . import transmissao
    account = db.first_account()
    ativo = whatsapp.configurado(account)
    lista = []
    if ativo:
        for t in db.listar_transmissoes(account["id"]):
            lista.append({**t, "relatorio": transmissao.relatorio(t["id"])})
    return templates.TemplateResponse(request, "transmissoes.html", {
        "account": account, "wa_configurado": ativo, "transmissoes": lista, "erro": ""})


@app.get("/transmissoes/nova")
def transmissao_nova(request: Request):
    guard = require_login(request)
    if guard:
        return guard
    from . import transmissao
    account = db.first_account()
    if not whatsapp.configurado(account):
        return _sem_wa(request)
    api.sincronizar_se_pendente(account)  # sem isso, template recém-aprovado não aparece
    tpls = [api._template_publico(t) for t in db.listar_templates(account["id"], True)]
    # um <optgroup> por pasta, na ordem das pastas; "Sem pasta" por último
    grupos = {p["nome"]: [] for p in db.listar_pastas(account["id"])}
    for t in tpls:
        grupos.setdefault(t["pasta"], []).append(t)
    grupos = [(nome, ts) for nome, ts in grupos.items() if ts and nome]
    sem_pasta = [t for t in tpls if not t["pasta"]]
    if sem_pasta:
        grupos.append(("", sem_pasta))
    campos = [r["key"] for r in db.conn().execute(
        """SELECT DISTINCT f.key FROM lead_fields f JOIN leads l ON l.id=f.lead_id
           WHERE l.account_id=? ORDER BY f.key""", (account["id"],))]
    return templates.TemplateResponse(request, "transmissao.html", {
        "account": account, "modo": "nova", "templates_wa": tpls, "grupos_tpl": grupos,
        "tags": db.all_tags(account["id"]), "campos": campos,
        "limite_diario": transmissao.limite_diario(account),
        "enviados_24h": db.templates_enviados_24h(account["id"]),
        "precos": {c: transmissao.preco(c) for c in transmissao.PRECOS_PADRAO_USD},
        "ritmo_min": RITMO_MIN, "ritmo_max": RITMO_MAX})


@app.post("/transmissoes")
async def transmissao_criar(request: Request):
    guard = require_login(request)
    if guard:
        return guard
    account = db.first_account()
    if not whatsapp.configurado(account):
        return _sem_wa(request)
    form = await request.form()
    nome_tpl, _, idioma = str(form.get("template", "")).partition("|")
    tpl = db.get_template(account["id"], nome_tpl, idioma or None)
    if not tpl or tpl["status"] != "APPROVED":
        return PlainTextResponse("Escolha um template aprovado.", status_code=400)
    variaveis = {v: str(form.get(f"var_{v}", "")) for v in api.variaveis_do_template(tpl)}
    publico = {"tipo": str(form.get("publico_tipo") or "todos"),
               "valor": str(form.get("publico_valor") or "").strip(),
               "campo_valor": str(form.get("campo_valor") or "").strip()}
    agendada = ""
    if form.get("quando") == "agendar":
        agendada = _brasilia_para_utc(str(form.get("data_hora") or ""))
        if not agendada:
            return PlainTextResponse("Data e hora inválidas.", status_code=400)
    try:
        ritmo = min(max(int(form.get("ritmo") or 20), RITMO_MIN), RITMO_MAX)
    except ValueError:
        ritmo = 20
    tid = db.criar_transmissao(account["id"], str(form.get("nome") or "").strip() or nome_tpl,
                               tpl["nome"], tpl["idioma"], tpl["categoria"], variaveis, publico,
                               agendada, ritmo)
    db.log_event("wa_transmissao_criada", account["id"], payload={
        "transmissao_id": tid, "publico": publico,
        "total": db.contar_publico(account["id"], publico)})
    return RedirectResponse(f"/transmissoes/{tid}", status_code=303)


@app.get("/transmissoes/{transmissao_id}")
def transmissao_ver(request: Request, transmissao_id: int, ver: str = ""):
    guard = require_login(request)
    if guard:
        return guard
    from . import transmissao
    account = db.first_account()
    t = db.get_transmissao(transmissao_id)
    if not t or not account or t["account_id"] != account["id"]:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "transmissao.html", {
        "account": account, "modo": "ver", "t": t, "r": transmissao.relatorio(t["id"]),
        "previsto": db.contar_publico(account["id"], t["publico"]),
        "ver": ver if ver in db.FILTROS_ENVIO else "",
        "envios": db.listar_envios(t["id"], ver), "explicar_erro": transmissao.explicar_erro})


def _muda_status(request, transmissao_id, de, para):
    guard = require_login(request)
    if guard:
        return guard
    account = db.first_account()
    t = db.get_transmissao(transmissao_id)
    if not t or not account or t["account_id"] != account["id"]:
        raise HTTPException(404)
    if t["status"] in de:
        db.set_status_transmissao(transmissao_id, para)
        db.log_event("wa_transmissao_" + para, account["id"],
                     payload={"transmissao_id": transmissao_id})
    return RedirectResponse(f"/transmissoes/{transmissao_id}", status_code=303)


@app.post("/transmissoes/{transmissao_id}/cancelar")
def transmissao_cancelar(request: Request, transmissao_id: int):
    return _muda_status(request, transmissao_id,
                        ("rascunho", "agendada", "enviando", "pausada"), "cancelada")


@app.post("/transmissoes/{transmissao_id}/disparar")
def transmissao_disparar(request: Request, transmissao_id: int):
    """Rascunho (criado pelo Claude) vira agendada: o worker de sempre envia."""
    return _muda_status(request, transmissao_id, ("rascunho",), "agendada")


@app.post("/transmissoes/{transmissao_id}/pausar")
def transmissao_pausar(request: Request, transmissao_id: int):
    return _muda_status(request, transmissao_id, ("enviando",), "pausada")


@app.post("/transmissoes/{transmissao_id}/retomar")
def transmissao_retomar(request: Request, transmissao_id: int):
    return _muda_status(request, transmissao_id, ("pausada",), "enviando")


# ---------- WhatsApp: importação de contatos ----------

import csv as _csv  # noqa: E402
import io as _io  # noqa: E402

LIMITE_IMPORTACAO = 20000
AVISO_CONSENTIMENTO = ("Marque a caixa de consentimento: só entra quem aceitou receber "
                       "suas mensagens.")


def importar_contatos(account_id, linhas, tag: str = "") -> dict:
    """Cada linha é (nome, telefone). Número inválido volta em `invalidos` com o texto
    original; válido vira lead (ou acha o que já existe) com opt-in de importação."""
    saida = {"importados": 0, "vinculados": 0, "invalidos": [], "conflitos": 0}
    for nome, telefone in linhas[:LIMITE_IMPORTACAO]:
        numero = whatsapp.normaliza_numero(telefone)
        if not numero:
            saida["invalidos"].append(f"{nome}, {telefone}".strip(", ") if nome else telefone)
            continue
        # planilha não é a Meta: o wa_id que veio do webhook é o que entrega, fica
        lead = db.lead_por_wa(account_id, numero, (nome or "").strip(), whatsapp.variantes(numero),
                              trocar_wa_id=False)
        db.registrar_optin(lead["id"], "importacao")
        if tag:
            db.add_tag(lead["id"], tag)
        saida["importados"] += 1
    return saida


def _linhas_do_texto(texto: str) -> list:
    linhas = []
    for bruta in (texto or "").splitlines():
        bruta = bruta.strip()
        if not bruta:
            continue
        sep = ";" if ";" in bruta else ","
        nome, _, tel = bruta.rpartition(sep)
        linhas.append(((nome if sep in bruta else "").strip(), (tel or bruta).strip()))
    return linhas


def _linhas_do_csv(conteudo: bytes) -> list:
    texto = conteudo.decode("utf-8-sig", errors="replace")
    try:
        dialeto = _csv.Sniffer().sniff(texto[:4096], delimiters=",;\t")
    except _csv.Error:
        class dialeto(_csv.excel):   # sem mexer no csv.excel global
            delimiter = ";" if texto.count(";") > texto.count(",") else ","
    leitor = _csv.DictReader(_io.StringIO(texto), dialect=dialeto)
    campos = {(c or "").strip().lower(): c for c in (leitor.fieldnames or [])}
    col_nome = campos.get("nome") or campos.get("name")
    col_tel = campos.get("telefone") or campos.get("whatsapp") or campos.get("celular")
    if not col_tel:
        return []
    return [((r.get(col_nome) or "") if col_nome else "", r.get(col_tel) or "")
            for r in leitor]


@app.get("/leads/importar")
def importar_page(request: Request):
    guard = require_login(request)
    if guard:
        return guard
    return templates.TemplateResponse(request, "importar.html", {
        "account": db.first_account(), "erro": "", "resultado": None,
        "limite": LIMITE_IMPORTACAO})


@app.post("/leads/importar")
async def importar_post(request: Request):
    guard = require_login(request)
    if guard:
        return guard
    account = db.first_account()
    form = await request.form()

    def pagina(erro="", resultado=None, status=200):
        return templates.TemplateResponse(request, "importar.html", {
            "account": account, "erro": erro, "resultado": resultado,
            "limite": LIMITE_IMPORTACAO}, status_code=status)

    if not account:
        return pagina("Conecte a conta do Instagram primeiro.", status=400)
    if form.get("consentimento") != "1":
        return pagina(AVISO_CONSENTIMENTO, status=400)

    linhas = _linhas_do_texto(str(form.get("texto") or ""))
    arquivo = form.get("arquivo")
    if arquivo is not None and hasattr(arquivo, "read"):
        linhas += _linhas_do_csv(await arquivo.read())
    if len(linhas) > LIMITE_IMPORTACAO:
        return pagina(f"Até {LIMITE_IMPORTACAO} contatos por envio; divida o arquivo.", status=400)
    tag = str(form.get("tag") or "").strip()
    resultado = importar_contatos(account["id"], linhas, tag)

    # leads do Instagram que já deram telefone num fluxo: só entram com a caixa
    # marcada (a spec não deixa campo antigo virar opt-in sozinho)
    if form.get("usar_campo_telefone") == "1":
        for lead in db.leads_com_campo(account["id"], "telefone"):
            numero = whatsapp.normaliza_numero(lead["valor"])
            if not numero:
                resultado["invalidos"].append(lead["valor"])
                continue
            if lead.get("wa_id"):
                # já tem número (webhook ou Pedir WhatsApp): o campo não troca; se for o
                # mesmo número, só ganha o consentimento
                if numero not in whatsapp.variantes(lead["wa_id"]):
                    continue
            elif db.vincular_whatsapp(lead["id"], numero,
                                      whatsapp.variantes(numero))["resultado"] == "conflito":
                resultado["conflitos"] += 1
                continue
            db.registrar_optin(lead["id"], "importacao")
            if tag:
                db.add_tag(lead["id"], tag)
            resultado["vinculados"] += 1

    db.log_event("wa_importacao", account["id"], payload={
        "importados": resultado["importados"], "vinculados": resultado["vinculados"],
        "invalidos": len(resultado["invalidos"]), "conflitos": resultado["conflitos"]})
    resultado["total_invalidos"] = len(resultado["invalidos"])
    resultado["invalidos"] = resultado["invalidos"][:50]
    return pagina(resultado=resultado)


# ---------- MCP: por último ----------
# Montado em "/" depois de todas as rotas: atende /mcp, /.well-known/oauth-* e as
# rotas OAuth do SDK (/authorize, /token, /register, /revoke). Qualquer outra coisa
# que não casou com o painel continua 404.
app.mount("/", mcp_server.PORTA)
