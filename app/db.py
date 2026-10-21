"""Camada de banco do comenta EU QUERO — SQLite embutido, zero configuração.

O arquivo fica em DATA_DIR/comentaeuquero.db (volume do Docker). A camada é
propositalmente fina: trocar por Postgres no futuro é reimplementar estas
funções, não reescrever o app.
"""
import json
import os
import secrets
import sqlite3
import uuid
import threading
import time
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DB_PATH = DATA_DIR / "comentaeuquero.db"

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ig_id TEXT NOT NULL UNIQUE,          -- id da Graph (recebe webhooks por ele)
    ig_user_id TEXT,                     -- user_id "clássico" (17841...)
    username TEXT,
    access_token TEXT NOT NULL,
    token_expires_at TEXT,               -- ISO UTC
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    keywords TEXT NOT NULL,              -- JSON: ["passo", "eu quero"]
    reply TEXT NOT NULL,                 -- suporta {username} e {link}
    public_reply TEXT DEFAULT '',        -- vazio = não responde no comentário
    link TEXT DEFAULT '',
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    ts TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    kind TEXT NOT NULL,                  -- webhook, private_reply, dm_reply, public_reply, oauth_ok, erro...
    rule_keyword TEXT DEFAULT '',
    source TEXT DEFAULT '',              -- comentario, story_reply, dm
    ok INTEGER,                          -- 1 sucesso / 0 falha / NULL n/a
    who TEXT DEFAULT '',                 -- username ou id de quem interagiu
    payload TEXT DEFAULT ''              -- JSON com detalhes
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_conta_ts ON events(account_id, ts);

CREATE TABLE IF NOT EXISTS processed (
    id TEXT PRIMARY KEY,                 -- comment_id ou mid
    ts TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    igsid TEXT NOT NULL,                 -- id da pessoa (IGSID nas mensagens; id do comentário p/ comentaristas)
    username TEXT DEFAULT '',
    name TEXT DEFAULT '',
    profile_pic TEXT DEFAULT '',
    followers INTEGER,
    is_follower INTEGER,                 -- 1 = segue a conta
    first_ts TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    last_ts TEXT,
    interactions INTEGER DEFAULT 0,
    last_keyword TEXT DEFAULT '',
    enriched INTEGER DEFAULT 0,
    UNIQUE(account_id, igsid)
);
"""

# Schema do motor de fluxo (v1). Separado do SCHEMA acima só por clareza — os dois
# rodam no mesmo executescript e são idempotentes (CREATE TABLE IF NOT EXISTS).
#
# O grafo mora em flows.graph como JSON no formato que o Vue Flow lê e escreve direto:
#
#   {"nodes": [{"id": "n1", "type": "text", "position": {"x": 0, "y": 0},
#               "data": {"text": "Oi {username}!"}}],
#    "edges": [{"id": "e1", "source": "n1", "target": "n2", "sourceHandle": null}]}
#
# Nós que ramificam (buttons, quick_replies, condition, split, wait_input) usam
# sourceHandle pra dizer QUAL saída a aresta representa: a chave do botão, "sim"/"nao",
# "a"/"b", "timeout". Aresta sem sourceHandle é a saída única (ou a padrão).
SCHEMA_FLOWS = """
CREATE TABLE IF NOT EXISTS flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'Sem nome',
    active INTEGER DEFAULT 1,
    graph TEXT NOT NULL DEFAULT '{"nodes":[],"edges":[]}',
    entry_node TEXT DEFAULT '',          -- id do primeiro nó (vazio = primeiro da lista)
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS triggers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_id INTEGER NOT NULL REFERENCES flows(id) ON DELETE CASCADE,
    type TEXT NOT NULL,                  -- comment | live_comment | story_reply | dm
    keywords TEXT NOT NULL DEFAULT '[]', -- JSON: ["aurora"]
    media_ids TEXT NOT NULL DEFAULT '[]',-- JSON: vazio = qualquer post/Reel
    public_reply TEXT DEFAULT '',        -- resposta no próprio comentário (só p/ comment/live_comment)
    active INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_triggers_flow ON triggers(flow_id);

CREATE TABLE IF NOT EXISTS flow_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    flow_id INTEGER NOT NULL REFERENCES flows(id) ON DELETE CASCADE,
    node_id TEXT DEFAULT '',             -- onde a pessoa parou
    waiting_for TEXT DEFAULT '',         -- '' | postback | text | quick_reply
    waiting_until TEXT DEFAULT '',       -- ISO UTC; vazio = sem timeout
    window_expires_at TEXT DEFAULT '',   -- fim da janela de 24h da Meta
    context TEXT NOT NULL DEFAULT '{}',  -- JSON acumulado no caminho (respostas, campos)
    status TEXT DEFAULT 'ativa',         -- ativa | concluida | expirada | erro
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_sessions_lead ON flow_sessions(lead_id, status);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON flow_sessions(status);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES flow_sessions(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,               -- nó a executar quando vencer
    run_at TEXT NOT NULL,                -- ISO UTC
    status TEXT DEFAULT 'pendente',      -- pendente | feito | expirado | erro
    detail TEXT DEFAULT '',
    created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_due ON jobs(status, run_at);

CREATE TABLE IF NOT EXISTS lead_tags (
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    ts TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (lead_id, tag)
);

CREATE TABLE IF NOT EXISTS ajustes (
    chave TEXT PRIMARY KEY,
    valor TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS lead_fields (
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    key TEXT NOT NULL,                   -- email, telefone, ou qualquer campo do fluxo
    value TEXT DEFAULT '',
    ts TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (lead_id, key)
);

-- Sessões do painel. Antes o cookie era HMAC fixo da senha: valor eterno, igual em
-- todo login, impossível de revogar sem trocar a senha. Agora cada login gera um
-- token aleatório com validade, e sair de verdade apaga a linha.
-- Cada mensagem que sai pelo WhatsApp, pelo wamid da Meta. É por aqui que o status
-- (entregue, lido, falhou) e o custo voltam pro fluxo ou pra transmissão certa.
CREATE TABLE IF NOT EXISTS wa_mensagens (
    wamid TEXT PRIMARY KEY,
    account_id INTEGER,
    lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
    envio_id INTEGER,
    flow_name TEXT DEFAULT '',
    origem TEXT DEFAULT '',              -- fluxo | template | transmissao
    status TEXT DEFAULT 'enviado',       -- enviado | entregue | lido | falhou
    categoria TEXT DEFAULT '',
    cobravel INTEGER DEFAULT 0,
    erro_codigo INTEGER,
    ts TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_wa_mensagens_conta_ts ON wa_mensagens(account_id, ts);

-- Templates do WhatsApp, espelho do que está na Meta (que é quem aprova). Sincronizar
-- apaga daqui o que sumiu de lá.
CREATE TABLE IF NOT EXISTS wa_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    nome TEXT,
    idioma TEXT,
    categoria TEXT,
    status TEXT,
    componentes TEXT DEFAULT '[]',
    sincronizado_em TEXT,
    UNIQUE(account_id, nome, idioma)
);

-- Transmissão = template aprovado mandado pra um público com opt-in, numa fila com
-- ritmo. Cada destinatário é uma linha em wa_envios, que guarda o funil dele.
CREATE TABLE IF NOT EXISTS transmissoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
    nome TEXT,
    template TEXT,
    idioma TEXT,
    categoria TEXT,
    variaveis TEXT DEFAULT '{}',
    publico TEXT DEFAULT '{}',
    agendada_para TEXT DEFAULT '',       -- ISO UTC; vazio = já
    ritmo_por_minuto INTEGER DEFAULT 20,
    status TEXT DEFAULT 'agendada',      -- rascunho | agendada | enviando | pausada | concluida | cancelada
    proximo_em REAL DEFAULT 0,           -- epoch do próximo envio permitido pelo ritmo
    criado_em TEXT,
    iniciado_em TEXT DEFAULT '',
    concluido_em TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS wa_envios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transmissao_id INTEGER REFERENCES transmissoes(id) ON DELETE CASCADE,
    lead_id INTEGER REFERENCES leads(id) ON DELETE SET NULL,
    wa_id TEXT,
    status TEXT DEFAULT 'pendente',      -- pendente | enviando | enviado | falhou | pulado | revisar
    wamid TEXT DEFAULT '',
    enviado_em TEXT DEFAULT '',
    entregue_em TEXT DEFAULT '',
    lido_em TEXT DEFAULT '',
    respondido_em TEXT DEFAULT '',
    falhou_em TEXT DEFAULT '',
    erro_codigo INTEGER,
    erro TEXT DEFAULT '',
    categoria TEXT DEFAULT '',
    cobravel INTEGER DEFAULT 0,
    adiar_ate REAL DEFAULT 0,            -- epoch; 131056 (par saturado) adia só este
    adiamentos INTEGER DEFAULT 0,
    UNIQUE(transmissao_id, lead_id)
);

CREATE INDEX IF NOT EXISTS idx_wa_envios_fila ON wa_envios(transmissao_id, status);
CREATE INDEX IF NOT EXISTS idx_wa_envios_lead ON wa_envios(lead_id);

CREATE TABLE IF NOT EXISTS painel_sessions (
    token TEXT PRIMARY KEY,
    criado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    expira_em TEXT NOT NULL,
    ip TEXT DEFAULT ''
);

-- Acesso do Claude (MCP). Guardamos só o SHA-256 do token: ele é aleatório de 256
-- bits, então não precisa do PBKDF2 lento da senha (que existe pra senha humana,
-- adivinhável). `tipo`: manual (gerado em Configurações), acesso e renovacao (do
-- login OAuth do Claude.ai). Revogar = apagar a linha.
CREATE TABLE IF NOT EXISTS mcp_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT NOT NULL UNIQUE,
    tipo TEXT NOT NULL,                  -- manual | acesso | renovacao
    cliente_id TEXT DEFAULT '',
    cliente_nome TEXT DEFAULT '',
    final TEXT DEFAULT '',               -- 4 últimos caracteres, pra reconhecer na tela
    criado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    expira_em TEXT DEFAULT '',           -- vazio = não vence (só o manual)
    ultimo_uso TEXT DEFAULT ''
);

-- Clientes OAuth registrados sozinhos (registro dinâmico, RFC 7591). O Claude.ai se
-- registra na primeira conexão; o dono só aprova no login do painel.
CREATE TABLE IF NOT EXISTS mcp_clientes (
    client_id TEXT PRIMARY KEY,
    nome TEXT DEFAULT '',
    dados TEXT NOT NULL DEFAULT '{}',    -- metadados do registro, como o cliente mandou
    criado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS mcp_codigos (
    hash TEXT PRIMARY KEY,
    dados TEXT NOT NULL,                 -- o pedido aprovado (PKCE, redirect, cliente)
    expira_em TEXT NOT NULL
);
"""


def conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    if c is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(DB_PATH, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=30000")
        _local.conn = c
    return c


def init():
    conn().executescript(SCHEMA)
    conn().executescript(SCHEMA_FLOWS)
    # migrações aditivas (retrocompatíveis — instâncias antigas atualizam sem quebrar)
    for ddl in [
        "ALTER TABLE accounts ADD COLUMN profile_pic TEXT DEFAULT ''",
        "ALTER TABLE rules ADD COLUMN flow_id INTEGER",  # regra já convertida em fluxo
        "ALTER TABLE triggers ADD COLUMN public_reply TEXT DEFAULT ''",
        "ALTER TABLE triggers ADD COLUMN public_replies TEXT DEFAULT '[]'",
        # job de envio adiado por rate limit precisa lembrar que a mensagem era uma
        # private reply: sem o comment_id, o replay viraria DM comum, e DM pra quem
        # nunca conversou com a conta a Meta recusa
        "ALTER TABLE jobs ADD COLUMN comment_id TEXT DEFAULT ''",
        # --- WhatsApp (1.8.0). O número mora na conta do Instagram: fluxos, leads e
        # gatilhos continuam por account_id, e instância sem WA fica com tudo vazio.
        "ALTER TABLE accounts ADD COLUMN wa_waba_id TEXT DEFAULT ''",
        "ALTER TABLE accounts ADD COLUMN wa_phone_number_id TEXT DEFAULT ''",
        "ALTER TABLE accounts ADD COLUMN wa_numero TEXT DEFAULT ''",
        "ALTER TABLE accounts ADD COLUMN wa_nome TEXT DEFAULT ''",
        "ALTER TABLE accounts ADD COLUMN wa_qualidade TEXT DEFAULT ''",
        "ALTER TABLE accounts ADD COLUMN wa_limite INTEGER",
        "ALTER TABLE accounts ADD COLUMN wa_estado_ts TEXT DEFAULT ''",
        # lead com os dois canais: wa_id é E.164 sem +; a janela de 24h passa a ser
        # por canal e mora no lead (a da sessão continua valendo pra sessão antiga)
        "ALTER TABLE leads ADD COLUMN wa_id TEXT DEFAULT ''",
        "ALTER TABLE leads ADD COLUMN ig_janela_ate TEXT DEFAULT ''",
        "ALTER TABLE leads ADD COLUMN wa_janela_ate TEXT DEFAULT ''",
        "ALTER TABLE leads ADD COLUMN wa_optin_em TEXT DEFAULT ''",
        "ALTER TABLE leads ADD COLUMN wa_optin_origem TEXT DEFAULT ''",
        "ALTER TABLE leads ADD COLUMN wa_optout_em TEXT DEFAULT ''",
        # por onde os próximos nós da sessão saem: ig | wa
        "ALTER TABLE flow_sessions ADD COLUMN canal TEXT DEFAULT 'ig'",
        # 131056 adia só o destinatário, a fila da transmissão segue
        "ALTER TABLE wa_envios ADD COLUMN adiar_ate REAL DEFAULT 0",
        "ALTER TABLE wa_envios ADD COLUMN adiamentos INTEGER DEFAULT 0",
        # índice depois dos ALTERs: em banco antigo a coluna wa_id só existe agora
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_wa ON leads(account_id, wa_id) "
        "WHERE wa_id <> ''",
    ]:
        try:
            conn().execute(ddl)
        except sqlite3.OperationalError:
            conn().rollback()  # coluna já existe; sem o rollback a transação fica aberta
    conn().commit()
    migrate_rules_to_flows()


# ---------- sessões do painel ----------

def criar_sessao(ip="", dias=30) -> str:
    token = secrets.token_urlsafe(32)
    conn().execute("INSERT INTO painel_sessions (token, expira_em, ip) VALUES (?,?,?)",
                   (token, in_seconds_iso(dias * 86400), ip[:45]))
    conn().commit()
    limpar_sessoes_vencidas()
    return token


def sessao_valida(token: str) -> bool:
    if not token:
        return False
    r = conn().execute("SELECT expira_em FROM painel_sessions WHERE token=?",
                       (token,)).fetchone()
    return bool(r) and r["expira_em"] > now_iso()


def apagar_sessao(token: str) -> None:
    if token:
        conn().execute("DELETE FROM painel_sessions WHERE token=?", (token,))
        conn().commit()


def apagar_todas_sessoes() -> int:
    cur = conn().execute("DELETE FROM painel_sessions")
    conn().commit()
    return cur.rowcount


def limpar_sessoes_vencidas() -> None:
    conn().execute("DELETE FROM painel_sessions WHERE expira_em <= ?", (now_iso(),))
    conn().commit()


# ---------- retenção de dados ----------

def apagar_lead(lead_id) -> bool:
    """Apaga o lead e tudo que pende dele (tags, campos, sessões) via ON DELETE CASCADE."""
    cur = conn().execute("DELETE FROM leads WHERE id=?", (lead_id,))
    conn().commit()
    return cur.rowcount > 0


def purgar_leads_antigos(dias: int) -> int:
    """Apaga leads sem interação há mais de `dias`. 0 ou negativo não faz nada.

    É o que faz a instância cumprir a política de privacidade em vez de só prometer:
    telefone e e-mail capturados num fluxo não ficam guardados pra sempre.
    """
    if not dias or dias <= 0:
        return 0
    limite = in_seconds_iso(-dias * 86400)
    cur = conn().execute(
        "DELETE FROM leads WHERE COALESCE(last_ts, first_ts) < ?", (limite,))
    conn().commit()
    return cur.rowcount


def purgar_eventos_antigos(dias: int) -> int:
    """Log técnico também tem prazo: guarda quem interagiu e o texto do que chegou."""
    if not dias or dias <= 0:
        return 0
    cur = conn().execute("DELETE FROM events WHERE ts < ?", (in_seconds_iso(-dias * 86400),))
    conn().commit()
    return cur.rowcount


# ---------- accounts ----------

def upsert_account(ig_id, ig_user_id, username, access_token, token_expires_at):
    conn().execute(
        """INSERT INTO accounts (ig_id, ig_user_id, username, access_token, token_expires_at)
           VALUES (?,?,?,?,?)
           ON CONFLICT(ig_id) DO UPDATE SET
             ig_user_id=excluded.ig_user_id, username=excluded.username,
             access_token=excluded.access_token, token_expires_at=excluded.token_expires_at""",
        (str(ig_id), str(ig_user_id or ""), username or "", access_token, token_expires_at))
    conn().commit()
    return get_account_by_ig_id(ig_id)


def get_account_by_ig_id(ig_id):
    r = conn().execute(
        "SELECT * FROM accounts WHERE ig_id=? OR ig_user_id=?",
        (str(ig_id), str(ig_id))).fetchone()
    return dict(r) if r else None


def id_da_instancia() -> str:
    """Identificador estável desta instalação, criado no primeiro uso.

    É um aleatório guardado no banco local, não derivado da conta do Instagram: dá
    pra contar quantas instâncias existem e em qual versão estão, sem que isso vire
    um jeito de saber de quem é cada perfil.
    """
    r = conn().execute("SELECT valor FROM ajustes WHERE chave='instancia_id'").fetchone()
    if r and r["valor"]:
        return r["valor"]
    novo = uuid.uuid4().hex
    conn().execute("INSERT OR REPLACE INTO ajustes (chave, valor) VALUES ('instancia_id', ?)",
                   (novo,))
    conn().commit()
    return novo


def proximo_da_rotacao(chave: str, total: int) -> int:
    """Próximo índice do rodízio de variações, e já avança o contador.

    O estado mora em `ajustes` (uma linha por nó) porque precisa sobreviver a
    restart: rodízio que zera toda vez que o container sobe manda a mesma primeira
    mensagem pra todo mundo, que é exatamente o que a variação existe pra evitar.
    """
    if total <= 1:
        return 0
    r = conn().execute("SELECT valor FROM ajustes WHERE chave=?", (chave,)).fetchone()
    atual = int(r["valor"]) if r and str(r["valor"] or "").isdigit() else -1
    proximo = (atual + 1) % total
    conn().execute(
        "INSERT INTO ajustes (chave, valor) VALUES (?,?) "
        "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (chave, str(proximo)))
    conn().commit()
    return proximo


def get_account(account_id):
    r = conn().execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
    return dict(r) if r else None


def first_account():
    r = conn().execute("SELECT * FROM accounts ORDER BY id LIMIT 1").fetchone()
    return dict(r) if r else None


def all_accounts():
    return [dict(r) for r in conn().execute("SELECT * FROM accounts ORDER BY id")]


def update_token(account_id, access_token, token_expires_at):
    conn().execute("UPDATE accounts SET access_token=?, token_expires_at=? WHERE id=?",
                   (access_token, token_expires_at, account_id))
    conn().commit()


def update_account_pic(account_id, profile_pic):
    conn().execute("UPDATE accounts SET profile_pic=? WHERE id=?", (profile_pic, account_id))
    conn().commit()


def delete_account(account_id):
    conn().execute("DELETE FROM accounts WHERE id=?", (account_id,))
    conn().commit()


# ---------- rules ----------

def list_rules(account_id=None, only_active=False):
    q = "SELECT * FROM rules"
    cond, args = [], []
    if account_id is not None:
        cond.append("account_id=?")
        args.append(account_id)
    if only_active:
        cond.append("active=1")
    if cond:
        q += " WHERE " + " AND ".join(cond)
    q += " ORDER BY id"
    out = []
    for r in conn().execute(q, args):
        d = dict(r)
        d["keywords"] = json.loads(d["keywords"])
        out.append(d)
    return out


def create_rule(account_id, keywords, reply, public_reply="", link="", active=1):
    cur = conn().execute(
        "INSERT INTO rules (account_id, keywords, reply, public_reply, link, active) VALUES (?,?,?,?,?,?)",
        (account_id, json.dumps(keywords, ensure_ascii=False), reply, public_reply, link, active))
    conn().commit()
    return cur.lastrowid


def update_rule(rule_id, keywords, reply, public_reply, link, active):
    conn().execute(
        "UPDATE rules SET keywords=?, reply=?, public_reply=?, link=?, active=? WHERE id=?",
        (json.dumps(keywords, ensure_ascii=False), reply, public_reply, link, active, rule_id))
    conn().commit()


def delete_rule(rule_id):
    conn().execute("DELETE FROM rules WHERE id=?", (rule_id,))
    conn().commit()


# ---------- events ----------

def log_event(kind, account_id=None, rule_keyword="", source="", ok=None, who="", payload=None):
    conn().execute(
        "INSERT INTO events (account_id, kind, rule_keyword, source, ok, who, payload) VALUES (?,?,?,?,?,?,?)",
        (account_id, kind, rule_keyword, source,
         None if ok is None else int(ok), who,
         json.dumps(payload, ensure_ascii=False)[:4000] if payload else ""))
    conn().commit()


def get_ajuste(chave, default=""):
    r = conn().execute("SELECT valor FROM ajustes WHERE chave=?", (chave,)).fetchone()
    return r["valor"] if r and r["valor"] else default


def set_ajuste(chave, valor):
    conn().execute("INSERT INTO ajustes (chave, valor) VALUES (?,?) "
                   "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                   (chave, str(valor)))
    conn().commit()


# Tudo que sai da instância pela API da Meta, com sucesso ou não. É o conjunto que
# se compara com o teto de rate limit (750 private replies/hora por conta, na doc).
KINDS_SAIDA = ("private_reply", "dm_reply", "fluxo_envio", "public_reply")


def envios_na_ultima_hora(account_id=None) -> int:
    kinds = list(KINDS_SAIDA)
    q = (f"SELECT COUNT(*) FROM events WHERE kind IN {_em(kinds)} "
         "AND ok IS NOT NULL AND ts >= ?")
    args = kinds + [in_seconds_iso(-3600)]
    if account_id is not None:
        q += " AND account_id=?"
        args.append(account_id)
    return conn().execute(q, args).fetchone()[0]


# Dois conjuntos de eventos porque o produto teve dois motores. O v0.2 gravava
# private_reply/dm_reply; o motor de fluxo grava fluxo_envio (cada mensagem que sai)
# e fluxo_inicio (cada pessoa que entrou num fluxo). O painel contava só os antigos,
# então instância nova, que nunca rodou o motor velho, mostrava zero pra sempre.
KINDS_ENVIO = ("private_reply", "dm_reply", "fluxo_envio")
KINDS_INICIO = ("private_reply", "dm_reply", "fluxo_inicio")


def _em(kinds):
    return "(" + ",".join("?" * len(kinds)) + ")"


def stats():
    c = conn()
    env, ini = list(KINDS_ENVIO), list(KINDS_INICIO)
    total = c.execute(
        f"SELECT COUNT(*) FROM events WHERE kind IN {_em(env)} AND ok=1", env).fetchone()[0]
    per_day = c.execute(
        f"""SELECT substr(ts,1,10) d, COUNT(*) n FROM events
            WHERE kind IN {_em(env)} AND ok=1
            GROUP BY d ORDER BY d DESC LIMIT 14""", env).fetchall()
    # por palavra-chave e por origem saem do início do fluxo, não do envio: um fluxo
    # de três mensagens é uma pessoa só, e o envio não guarda de onde ela veio
    per_rule = c.execute(
        f"""SELECT rule_keyword k, COUNT(*) n FROM events
            WHERE kind IN {_em(ini)} AND ok=1 GROUP BY k ORDER BY n DESC""", ini).fetchall()
    per_source = c.execute(
        f"""SELECT source s, COUNT(*) n FROM events
            WHERE kind IN {_em(ini)} AND ok=1 GROUP BY s ORDER BY n DESC""", ini).fetchall()
    last = c.execute(
        f"""SELECT ts, source, rule_keyword, who, ok FROM events
            WHERE kind IN {_em(ini)} ORDER BY id DESC LIMIT 20""", ini).fetchall()
    fails = c.execute(
        f"SELECT COUNT(*) FROM events WHERE kind IN {_em(env)} AND ok=0", env).fetchone()[0]
    return {
        "total": total, "fails": fails,
        "per_day": [(r["d"], r["n"]) for r in per_day],
        "per_rule": [(r["k"] or "?", r["n"]) for r in per_rule],
        "per_source": [(r["s"] or "?", r["n"]) for r in per_source],
        "last": [dict(r) for r in last],
    }


def funil(account_id, dias=0, flow_name=None):
    """Funil por fluxo, contando PESSOAS distintas em cada etapa.

    acionaram  -> dispararam o gatilho (fluxo_inicio)
    entregues  -> receberam ao menos a primeira mensagem (fluxo_envio ok=1)
    leram      -> o Instagram avisou leitura (fluxo_lido)
    avancaram  -> clicaram num botão de continuar ou responderam (postback/quick/texto)

    O clique em botão de LINK não entra: a Meta não reporta, o clique abre no navegador
    da pessoa. Por isso um fluxo que termina em botão de link mede até 'leram'.
    Conta por `who` (o @ da pessoa), que é como o evento identifica quem interagiu.
    """
    corte = in_seconds_iso(-dias * 86400) if dias else ""
    etapas = {
        "acionaram": "kind='fluxo_inicio' AND ok=1",
        "entregues": "kind='fluxo_envio' AND ok=1",
        "leram": "kind='fluxo_lido'",
        "avancaram": "kind IN ('fluxo_postback','fluxo_quick_reply','fluxo_resposta') AND ok=1",
    }
    def _extra(args):
        sql = ""
        if corte:
            sql += " AND ts>=?"
            args.append(corte)
        if flow_name is not None:
            sql += " AND rule_keyword=?"
            args.append(flow_name)
        return sql

    por_fluxo = {}
    for etapa, cond in etapas.items():
        args = [account_id]
        sql = (f"SELECT rule_keyword f, COUNT(DISTINCT who) n FROM events "
               f"WHERE account_id=? AND {cond} AND who<>''" + _extra(args) + " GROUP BY rule_keyword")
        for r in conn().execute(sql, args):
            por_fluxo.setdefault(r["f"] or "?", {})[etapa] = r["n"]

    # mensagens entregues no total (não pessoas): um fluxo de 3 mensagens conta 3
    msgs = {}
    args = [account_id]
    sql = ("SELECT rule_keyword f, COUNT(*) n FROM events WHERE account_id=? "
           "AND kind='fluxo_envio' AND ok=1" + _extra(args) + " GROUP BY rule_keyword")
    for r in conn().execute(sql, args):
        msgs[r["f"] or "?"] = r["n"]

    ativos = {f["name"] for f in list_flows(account_id)}
    linhas = []
    for nome, e in sorted(por_fluxo.items(), key=lambda x: -x[1].get("acionaram", 0)):
        linhas.append({
            "fluxo": nome,
            "existe": nome in ativos,
            "acionaram": e.get("acionaram", 0),
            "entregues": e.get("entregues", 0),
            "leram": e.get("leram", 0),
            "avancaram": e.get("avancaram", 0),
            "mensagens": msgs.get(nome, 0),
        })
    return linhas


# ---------- leads ----------

def touch_lead(account_id, igsid, keyword="", username=""):
    """Registra interação do lead (cria se novo). Retorna o lead atualizado."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn().execute(
        """INSERT INTO leads (account_id, igsid, username, last_ts, interactions, last_keyword)
           VALUES (?,?,?,?,1,?)
           ON CONFLICT(account_id, igsid) DO UPDATE SET
             last_ts=excluded.last_ts,
             interactions=interactions+1,
             last_keyword=CASE WHEN excluded.last_keyword!='' THEN excluded.last_keyword ELSE last_keyword END,
             username=CASE WHEN excluded.username!='' THEN excluded.username ELSE username END""",
        (account_id, str(igsid), username, now, keyword))
    conn().commit()
    r = conn().execute("SELECT * FROM leads WHERE account_id=? AND igsid=?",
                       (account_id, str(igsid))).fetchone()
    return dict(r)


def enrich_lead(account_id, igsid, profile: dict):
    conn().execute(
        """UPDATE leads SET username=COALESCE(NULLIF(?, ''), username), name=?, profile_pic=?,
           followers=?, is_follower=?, enriched=1
           WHERE account_id=? AND igsid=?""",
        (profile.get("username", ""), profile.get("name", ""), profile.get("profile_pic", ""),
         profile.get("follower_count"),
         1 if profile.get("is_user_follow_business") else 0,
         account_id, str(igsid)))
    conn().commit()


ORDENS_LEADS = {
    "recente": "COALESCE(last_ts, first_ts) DESC",
    "antigo": "COALESCE(last_ts, first_ts) ASC",
    "seguidores": "followers DESC NULLS LAST",
    "interacoes": "interactions DESC",
    "nome": "LOWER(COALESCE(NULLIF(name,''), username)) ASC",
}


def list_leads(account_id, limit=200, keyword=None, segue=None, busca=None,
               ordem="recente", tag=None, desde=None, ate=None, offset=0):
    """Leads com filtro. Cada filtro é opcional e eles se combinam.

    keyword: só quem chegou por essa palavra
    segue:   1 só seguidores, 0 só quem não segue
    busca:   trecho do nome ou do @
    tag:     só quem tem a etiqueta
    desde/ate: ISO UTC, recorte pela primeira interação (first_ts)
    """
    onde, args = ["account_id=?"], [account_id]
    if tag:
        onde.append("EXISTS (SELECT 1 FROM lead_tags t WHERE t.lead_id=leads.id AND t.tag=?)")
        args.append(tag)
    if desde:
        onde.append("first_ts>=?")
        args.append(desde)
    if ate:
        onde.append("first_ts<?")
        args.append(ate)
    if keyword:
        onde.append("last_keyword=?")
        args.append(keyword)
    if segue in (0, 1):
        onde.append("is_follower=?")
        args.append(segue)
    if busca:
        onde.append("(LOWER(username) LIKE ? OR LOWER(name) LIKE ?)")
        alvo = f"%{busca.lower().strip().lstrip('@')}%"
        args += [alvo, alvo]
    ordenacao = ORDENS_LEADS.get(ordem, ORDENS_LEADS["recente"])
    args += [limit, max(0, int(offset or 0))]
    return [dict(r) for r in conn().execute(
        f"SELECT * FROM leads WHERE {' AND '.join(onde)} ORDER BY {ordenacao}, id DESC "
        "LIMIT ? OFFSET ?", args)]


def leads_resumo(account_id) -> dict:
    """Números do topo da página e as palavras disponíveis pra filtrar."""
    c = conn()
    total = c.execute("SELECT COUNT(*) FROM leads WHERE account_id=?",
                      (account_id,)).fetchone()[0]
    seguidores = c.execute(
        "SELECT COUNT(*) FROM leads WHERE account_id=? AND is_follower=1",
        (account_id,)).fetchone()[0]
    palavras = [(r["k"], r["n"]) for r in c.execute(
        """SELECT last_keyword k, COUNT(*) n FROM leads
           WHERE account_id=? AND last_keyword != ''
           GROUP BY last_keyword ORDER BY n DESC""", (account_id,))]
    return {"total": total, "seguidores": seguidores, "palavras": palavras}


def leads_count(account_id):
    return conn().execute("SELECT COUNT(*) FROM leads WHERE account_id=?", (account_id,)).fetchone()[0]


def leads_by_who(account_id):
    """Mapa username/igsid -> {pic, name} pra thread do painel."""
    out = {}
    for r in conn().execute("SELECT igsid, username, name, profile_pic FROM leads WHERE account_id=?",
                            (account_id,)):
        info = {"pic": r["profile_pic"], "name": r["name"] or r["username"]}
        out[r["igsid"]] = info
        if r["username"]:
            out[r["username"]] = info
    return out


# ---------- processed (dedupe) ----------

def claim(item_id: str) -> bool:
    """True se este id ainda não foi processado (e marca atomicamente).

    O rollback não é decoração. Sem ele, o INSERT que bate na chave duplicada (ou
    seja, toda reentrega de webhook da Meta, que é rotina) deixava a transação
    ABERTA nesta conexão para sempre. Como a transação segura o lock de escrita do
    SQLite, o app inteiro parava de gravar: webhook virava 500, fluxo não rodava,
    login não entrava — tudo com o banco aparentemente saudável e o /health
    respondendo 200. Foi o que derrubou a instância em 22/07/2026.
    """
    try:
        conn().execute("INSERT INTO processed (id) VALUES (?)", (str(item_id),))
        conn().commit()
        return True
    except sqlite3.IntegrityError:
        conn().rollback()
        return False
    except sqlite3.OperationalError:
        conn().rollback()
        raise


def cleanup(days=30):
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - days * 86400))
    conn().execute("DELETE FROM processed WHERE ts < ?", (cutoff,))
    conn().execute("DELETE FROM events WHERE ts < ? AND kind='webhook'", (cutoff,))
    conn().commit()


# ---------- helpers de tempo ----------

def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def in_seconds_iso(seconds: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + seconds))


# ---------- flows ----------

def _flow_row(r) -> dict:
    d = dict(r)
    d["graph"] = json.loads(d["graph"] or '{"nodes":[],"edges":[]}')
    return d


def create_flow(account_id, name="Sem nome", graph=None, entry_node="", active=1):
    graph = graph or {"nodes": [], "edges": []}
    cur = conn().execute(
        "INSERT INTO flows (account_id, name, active, graph, entry_node) VALUES (?,?,?,?,?)",
        (account_id, name, active, json.dumps(graph, ensure_ascii=False), entry_node))
    conn().commit()
    return cur.lastrowid


def get_flow(flow_id):
    r = conn().execute("SELECT * FROM flows WHERE id=?", (flow_id,)).fetchone()
    return _flow_row(r) if r else None


def list_flows(account_id=None, only_active=False):
    q, cond, args = "SELECT * FROM flows", [], []
    if account_id is not None:
        cond.append("account_id=?")
        args.append(account_id)
    if only_active:
        cond.append("active=1")
    if cond:
        q += " WHERE " + " AND ".join(cond)
    return [_flow_row(r) for r in conn().execute(q + " ORDER BY id", args)]


def update_flow(flow_id, name=None, graph=None, entry_node=None, active=None):
    sets, args = ["updated_at=?"], [now_iso()]
    for col, val in (("name", name), ("entry_node", entry_node), ("active", active)):
        if val is not None:
            sets.append(f"{col}=?")
            args.append(val)
    if graph is not None:
        sets.append("graph=?")
        args.append(json.dumps(graph, ensure_ascii=False))
    args.append(flow_id)
    conn().execute(f"UPDATE flows SET {', '.join(sets)} WHERE id=?", args)
    conn().commit()


def delete_flow(flow_id):
    conn().execute("DELETE FROM flows WHERE id=?", (flow_id,))
    conn().commit()


def flow_stats(account_id) -> dict:
    """Entregas por fluxo, somando os dois motores.

    O motor antigo gravava o evento com a palavra-chave em rule_keyword; o novo grava
    o nome do fluxo no mesmo campo. Como a migração nomeou cada fluxo com a própria
    palavra-chave, os dois somam naturalmente. Fluxo renomeado depois perde o
    histórico antigo, e tudo bem: o número é indicativo, não contábil.
    """
    saida = {}
    for r in conn().execute(
            """SELECT rule_keyword k, COUNT(*) n, MAX(ts) ultimo FROM events
               WHERE account_id=? AND ok=1
                 AND kind IN ('private_reply','dm_reply','fluxo_envio')
               GROUP BY rule_keyword""", (account_id,)):
        saida[r["k"]] = {"entregas": r["n"], "ultimo": r["ultimo"]}
    return saida


# ---------- triggers ----------

def _trigger_row(r) -> dict:
    d = dict(r)
    d["keywords"] = json.loads(d["keywords"] or "[]")
    d["media_ids"] = json.loads(d["media_ids"] or "[]")
    # a resposta pública virou lista. Gatilho antigo tem só a coluna de texto, então
    # ela conta como a primeira da lista e ninguém precisa reconfigurar nada.
    lista = json.loads(d.get("public_replies") or "[]")
    if not lista and d.get("public_reply"):
        lista = [d["public_reply"]]
    d["public_replies"] = lista
    d["public_reply"] = lista[0] if lista else ""
    return d


def add_trigger(flow_id, type_, keywords=None, media_ids=None, public_reply="",
                public_replies=None, active=1):
    lista = [t for t in (public_replies or []) if (t or "").strip()]
    if not lista and (public_reply or "").strip():
        lista = [public_reply]
    cur = conn().execute(
        """INSERT INTO triggers (flow_id, type, keywords, media_ids, public_reply,
                                 public_replies, active)
           VALUES (?,?,?,?,?,?,?)""",
        (flow_id, type_, json.dumps(keywords or [], ensure_ascii=False),
         json.dumps(media_ids or [], ensure_ascii=False), lista[0] if lista else "",
         json.dumps(lista, ensure_ascii=False), active))
    conn().commit()
    return cur.lastrowid


def list_triggers(flow_id):
    return [_trigger_row(r) for r in conn().execute(
        "SELECT * FROM triggers WHERE flow_id=? ORDER BY id", (flow_id,))]


def set_trigger_active(trigger_id, active: int):
    """Liga ou desliga um gatilho sem apagá-lo. Desligar é o que a pessoa quer quando
    está testando: some do ar, mas as palavras-chave e os posts escolhidos continuam
    guardados pra quando religar."""
    conn().execute("UPDATE triggers SET active=? WHERE id=?", (1 if active else 0, trigger_id))
    conn().commit()


def delete_trigger(trigger_id):
    conn().execute("DELETE FROM triggers WHERE id=?", (trigger_id,))
    conn().commit()


def active_triggers(account_id, type_=None):
    """Gatilhos ativos de fluxos ativos. É o que o motor consulta a cada webhook."""
    q = """SELECT t.*, f.name AS flow_name FROM triggers t
           JOIN flows f ON f.id = t.flow_id
           WHERE f.account_id=? AND f.active=1 AND t.active=1"""
    args = [account_id]
    if type_:
        q += " AND t.type=?"
        args.append(type_)
    return [_trigger_row(r) for r in conn().execute(q + " ORDER BY t.id", args)]


# ---------- sessões de fluxo ----------

def _session_row(r) -> dict:
    d = dict(r)
    d["context"] = json.loads(d["context"] or "{}")
    return d


def open_session(account_id, lead_id, flow_id, node_id="", window_expires_at="", context=None,
                 canal="ig"):
    cur = conn().execute(
        """INSERT INTO flow_sessions (account_id, lead_id, flow_id, node_id,
                                      window_expires_at, context, canal)
           VALUES (?,?,?,?,?,?,?)""",
        (account_id, lead_id, flow_id, node_id, window_expires_at,
         json.dumps(context or {}, ensure_ascii=False), canal or "ig"))
    conn().commit()
    return cur.lastrowid


def get_session(session_id):
    r = conn().execute("SELECT * FROM flow_sessions WHERE id=?", (session_id,)).fetchone()
    return _session_row(r) if r else None


def active_session_for_lead(lead_id):
    """Sessão ativa mais recente do lead. É por ela que uma resposta livre encontra
    o fluxo em que a pessoa está parada."""
    r = conn().execute(
        """SELECT * FROM flow_sessions WHERE lead_id=? AND status='ativa'
           ORDER BY id DESC LIMIT 1""", (lead_id,)).fetchone()
    return _session_row(r) if r else None


def flow_name_do_lead(lead_id):
    """Nome do fluxo mais recente em que o lead entrou, ativo ou não. Serve pra atribuir
    ao fluxo certo eventos que chegam soltos (leitura, clique), já que o webhook não diz
    de qual fluxo veio — num fluxo de uma mensagem só, a sessão já está concluída quando
    a leitura chega."""
    r = conn().execute(
        """SELECT f.name FROM flow_sessions s JOIN flows f ON f.id = s.flow_id
           WHERE s.lead_id=? ORDER BY s.id DESC LIMIT 1""", (lead_id,)).fetchone()
    return r["name"] if r else ""


def update_session(session_id, node_id=None, waiting_for=None, waiting_until=None,
                   context=None, status=None, window_expires_at=None, canal=None):
    sets, args = ["updated_at=?"], [now_iso()]
    for col, val in (("node_id", node_id), ("waiting_for", waiting_for),
                     ("waiting_until", waiting_until), ("status", status),
                     ("window_expires_at", window_expires_at), ("canal", canal)):
        if val is not None:
            sets.append(f"{col}=?")
            args.append(val)
    if context is not None:
        sets.append("context=?")
        args.append(json.dumps(context, ensure_ascii=False))
    args.append(session_id)
    conn().execute(f"UPDATE flow_sessions SET {', '.join(sets)} WHERE id=?", args)
    conn().commit()


def sessions_past_timeout():
    """Sessões esperando resposta cujo prazo venceu. O worker manda pela aresta 'timeout'."""
    return [_session_row(r) for r in conn().execute(
        """SELECT * FROM flow_sessions
           WHERE status='ativa' AND waiting_until != '' AND waiting_until <= ?""",
        (now_iso(),))]


# ---------- jobs (delay / agendamento) ----------

def schedule_job(session_id, node_id, run_at, comment_id=""):
    cur = conn().execute(
        "INSERT INTO jobs (session_id, node_id, run_at, comment_id) VALUES (?,?,?,?)",
        (session_id, node_id, run_at, comment_id or ""))
    conn().commit()
    return cur.lastrowid


def due_jobs(limit=50):
    return [dict(r) for r in conn().execute(
        "SELECT * FROM jobs WHERE status='pendente' AND run_at <= ? ORDER BY run_at LIMIT ?",
        (now_iso(), limit))]


def claim_job(job_id) -> bool:
    """Marca o job como em execução. False se outro worker já pegou."""
    cur = conn().execute(
        "UPDATE jobs SET status='rodando' WHERE id=? AND status='pendente'", (job_id,))
    conn().commit()
    return cur.rowcount == 1


def finish_job(job_id, status="feito", detail=""):
    conn().execute("UPDATE jobs SET status=?, detail=? WHERE id=?",
                   (status, detail[:500], job_id))
    conn().commit()


def cancel_jobs_of_session(session_id):
    conn().execute("UPDATE jobs SET status='cancelado' WHERE session_id=? AND status='pendente'",
                   (session_id,))
    conn().commit()


# ---------- tags e campos do lead ----------

def add_tag(lead_id, tag):
    conn().execute("INSERT OR IGNORE INTO lead_tags (lead_id, tag) VALUES (?,?)",
                   (lead_id, tag))
    conn().commit()


def remove_tag(lead_id, tag):
    conn().execute("DELETE FROM lead_tags WHERE lead_id=? AND tag=?", (lead_id, tag))
    conn().commit()


def lead_tags(lead_id):
    return [r["tag"] for r in conn().execute(
        "SELECT tag FROM lead_tags WHERE lead_id=? ORDER BY tag", (lead_id,))]


def has_tag(lead_id, tag) -> bool:
    return conn().execute("SELECT 1 FROM lead_tags WHERE lead_id=? AND tag=?",
                          (lead_id, tag)).fetchone() is not None


def all_tags(account_id):
    """Tags em uso na conta, com contagem — alimenta o seletor do editor."""
    return [(r["tag"], r["n"]) for r in conn().execute(
        """SELECT t.tag, COUNT(*) n FROM lead_tags t
           JOIN leads l ON l.id = t.lead_id
           WHERE l.account_id=? GROUP BY t.tag ORDER BY n DESC""", (account_id,))]


def set_field(lead_id, key, value):
    conn().execute(
        """INSERT INTO lead_fields (lead_id, key, value, ts) VALUES (?,?,?,?)
           ON CONFLICT(lead_id, key) DO UPDATE SET value=excluded.value, ts=excluded.ts""",
        (lead_id, key, str(value), now_iso()))
    conn().commit()


def get_field(lead_id, key, default=""):
    r = conn().execute("SELECT value FROM lead_fields WHERE lead_id=? AND key=?",
                       (lead_id, key)).fetchone()
    return r["value"] if r else default


def lead_fields(lead_id) -> dict:
    return {r["key"]: r["value"] for r in conn().execute(
        "SELECT key, value FROM lead_fields WHERE lead_id=?", (lead_id,))}


def get_lead(lead_id):
    r = conn().execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    return dict(r) if r else None


# ---------- migração rules -> flows ----------

def migrate_rules_to_flows():
    """Cada regra do modelo antigo vira um fluxo de um nó só, com os mesmos gatilhos
    que o engine v0.2 atendia (comentário, resposta de story e DM).

    Idempotente: regra já convertida tem flow_id preenchido e é pulada. Não apaga
    nem altera a tabela rules — o motor antigo continua funcionando enquanto o novo
    não assume, e dá pra rodar os dois lado a lado durante o cutover.
    """
    pendentes = conn().execute(
        "SELECT * FROM rules WHERE flow_id IS NULL ORDER BY id").fetchall()
    convertidas, ultima_conta = 0, None
    for r in pendentes:
        rule = dict(r)
        ultima_conta = rule["account_id"]
        keywords = json.loads(rule["keywords"])
        node = {
            "id": "n1",
            "type": "text",
            "position": {"x": 0, "y": 0},
            "data": {"text": rule["reply"], "link": rule.get("link") or ""},
        }
        graph = {"nodes": [node], "edges": []}
        # a resposta pública era campo da regra; no modelo novo pertence ao gatilho
        public_reply = rule.get("public_reply") or ""
        name = (keywords[0] if keywords else "regra").strip() or "regra"
        flow_id = create_flow(rule["account_id"], name=name, graph=graph,
                              entry_node="n1", active=rule.get("active", 1))
        for tipo in ("comment", "story_reply", "dm"):
            add_trigger(flow_id, tipo, keywords=keywords,
                        public_reply=public_reply if tipo == "comment" else "")
        conn().execute("UPDATE rules SET flow_id=? WHERE id=?", (flow_id, rule["id"]))
        conn().commit()
        convertidas += 1
    if convertidas:
        log_event("migracao_rules_flows", ultima_conta, payload={"convertidas": convertidas})
    return convertidas


# ---------- whatsapp ----------
#
# Lead que só existe no WhatsApp ganha igsid "wa:<wa_id>". A coluna igsid é NOT NULL
# e única por conta, e trocar isso no SQLite exige recriar a tabela (com quatro FKs
# apontando pra ela), o que a migração idempotente não faz. O prefixo é o jeito de
# caber no esquema de hoje sem colidir com IGSID de verdade, que é só dígito.

PREFIXO_SO_WA = "wa:"
CANAIS = ("ig", "wa")


def e_so_wa(lead: dict) -> bool:
    return str((lead or {}).get("igsid") or "").startswith(PREFIXO_SO_WA)


def get_account_by_wa_phone(phone_number_id: str):
    if not phone_number_id:
        return None
    r = conn().execute("SELECT * FROM accounts WHERE wa_phone_number_id=? LIMIT 1",
                       (str(phone_number_id),)).fetchone()
    return dict(r) if r else None


def set_wa_config(account_id, waba_id: str, phone_number_id: str) -> None:
    """Grava os IDs do número. Os dois vazios = desconectar (limpa o estado junto,
    pra o painel não mostrar nome e limite de um número que não está mais ligado)."""
    if not waba_id and not phone_number_id:
        conn().execute(
            """UPDATE accounts SET wa_waba_id='', wa_phone_number_id='', wa_numero='',
               wa_nome='', wa_qualidade='', wa_limite=NULL, wa_estado_ts='' WHERE id=?""",
            (account_id,))
    else:
        conn().execute("UPDATE accounts SET wa_waba_id=?, wa_phone_number_id=? WHERE id=?",
                       (waba_id or "", phone_number_id or "", account_id))
    conn().commit()


def update_wa_estado(account_id, numero: str, nome: str, qualidade: str, limite) -> None:
    conn().execute(
        """UPDATE accounts SET wa_numero=?, wa_nome=?, wa_qualidade=?, wa_limite=?,
           wa_estado_ts=? WHERE id=?""",
        (numero or "", nome or "", qualidade or "", limite, now_iso(), account_id))
    conn().commit()


def _lead_por_variantes(account_id, variantes, exceto=None):
    variantes = [v for v in (variantes or []) if v]
    if not variantes:
        return None
    q = f"SELECT * FROM leads WHERE account_id=? AND wa_id IN {_em(variantes)}"
    args = [account_id] + list(variantes)
    if exceto is not None:
        q += " AND id<>?"
        args.append(exceto)
    r = conn().execute(q + " ORDER BY id LIMIT 1", args).fetchone()
    return dict(r) if r else None


def lead_por_wa(account_id, wa_id: str, nome: str = "", variantes=None,
                trocar_wa_id: bool = True) -> dict:
    """Lead dono deste número (procurando também a forma com/sem o 9), ou um lead
    só-WA novo. O wa_id gravado vira o que a Meta mandou: é por ele que ela entrega.

    `trocar_wa_id=False` é pra quem não fala pela Meta (importação de planilha): acha
    o lead pelas variantes mas mantém o wa_id que já estava gravado."""
    wa_id = str(wa_id)
    variantes = list(variantes or [wa_id])
    if wa_id not in variantes:
        variantes.insert(0, wa_id)
    achado = _lead_por_variantes(account_id, variantes)
    agora = now_iso()
    if achado:
        conn().execute(
            """UPDATE leads SET last_ts=?, interactions=interactions+1, wa_id=?,
               name=CASE WHEN COALESCE(name,'')='' THEN ? ELSE name END WHERE id=?""",
            (agora, wa_id if trocar_wa_id or not achado.get("wa_id") else achado["wa_id"],
             nome or "", achado["id"]))
        conn().commit()
        return get_lead(achado["id"])
    cur = conn().execute(
        """INSERT INTO leads (account_id, igsid, name, last_ts, interactions, wa_id)
           VALUES (?,?,?,?,1,?)""",
        (account_id, PREFIXO_SO_WA + wa_id, nome or "", agora, wa_id))
    conn().commit()
    return get_lead(cur.lastrowid)


def _funde_so_wa_no_ig(c, so_wa: dict, ig: dict) -> None:
    """Leva tudo do lead só-WA pro lead do IG. Em conflito de campo vale o do IG.
    Roda dentro da transação de vincular_whatsapp (sem commit aqui)."""
    c.execute("INSERT OR IGNORE INTO lead_tags (lead_id, tag, ts) "
              "SELECT ?, tag, ts FROM lead_tags WHERE lead_id=?", (ig["id"], so_wa["id"]))
    c.execute("INSERT OR IGNORE INTO lead_fields (lead_id, key, value, ts) "
              "SELECT ?, key, value, ts FROM lead_fields WHERE lead_id=?",
              (ig["id"], so_wa["id"]))
    c.execute("UPDATE flow_sessions SET lead_id=? WHERE lead_id=?", (ig["id"], so_wa["id"]))
    for tabela in ("wa_mensagens", "wa_envios"):
        try:
            c.execute(f"UPDATE {tabela} SET lead_id=? WHERE lead_id=?", (ig["id"], so_wa["id"]))
        except sqlite3.OperationalError:
            pass   # tabela ainda não existe nesta versão do banco
    janela = max(ig.get("wa_janela_ate") or "", so_wa.get("wa_janela_ate") or "")
    optin_em, optin_origem = ig.get("wa_optin_em") or "", ig.get("wa_optin_origem") or ""
    if not optin_em:
        optin_em, optin_origem = so_wa.get("wa_optin_em") or "", so_wa.get("wa_optin_origem") or ""
    optout = so_wa.get("wa_optout_em") or ig.get("wa_optout_em") or ""
    # zera o wa_id do só-WA antes de gravar no do IG: o índice único é por número
    c.execute("UPDATE leads SET wa_id='' WHERE id=?", (so_wa["id"],))
    c.execute("DELETE FROM leads WHERE id=?", (so_wa["id"],))
    c.execute(
        """UPDATE leads SET wa_janela_ate=?, wa_optin_em=?, wa_optin_origem=?,
           wa_optout_em=? WHERE id=?""",
        (janela, optin_em, optin_origem, optout, ig["id"]))


def _uma_sessao_ativa(c, lead_id, manter=None) -> list:
    """Depois da fusão o lead pode ter herdado uma segunda sessão ativa. Fica só uma:
    `manter` (a que está rodando agora) se ainda estiver ativa, senão a mais recente.
    As outras são encerradas com motivo no contexto e jobs cancelados. Devolve os ids
    encerrados. Sem commit (roda na transação de vincular_whatsapp)."""
    ativas = [dict(r) for r in c.execute(
        """SELECT id, context FROM flow_sessions WHERE lead_id=? AND status='ativa'
           ORDER BY updated_at DESC, id DESC""", (lead_id,))]
    if len(ativas) < 2:
        return []
    ids = [a["id"] for a in ativas]
    fica = manter if manter in ids else ids[0]
    encerradas = []
    for a in ativas:
        if a["id"] == fica:
            continue
        try:
            ctx = json.loads(a["context"] or "{}")
        except ValueError:
            ctx = {}
        ctx["encerrada_motivo"] = "fusao_de_leads"
        c.execute("UPDATE flow_sessions SET status='concluida', context=?, updated_at=? WHERE id=?",
                  (json.dumps(ctx, ensure_ascii=False), now_iso(), a["id"]))
        c.execute("UPDATE jobs SET status='cancelado' WHERE session_id=? AND status='pendente'",
                  (a["id"],))
        encerradas.append(a["id"])
    return encerradas


def vincular_whatsapp(lead_id, wa_id: str, variantes=None, sessao_atual=None) -> dict:
    """O lead do IG informou este número. Resultado:

    vinculado     o número era de ninguém, agora é deste lead
    ja_vinculado  já era deste lead
    fundido       era de um lead só-WA, que foi absorvido por este
    conflito      é de outro lead do IG; quem informou primeiro fica com ele

    Em todos os casos o campo `whatsapp` do lead guarda o número informado. Na fusão,
    se os dois tinham fluxo em andamento, só um continua (ver _uma_sessao_ativa);
    `sessao_atual` é a sessão que pediu o número, que tem preferência.
    """
    wa_id = str(wa_id)
    variantes = list(variantes or [wa_id])
    if wa_id not in variantes:
        variantes.insert(0, wa_id)
    lead = get_lead(lead_id)
    if not lead:
        return {"resultado": "conflito", "lead_id": lead_id}
    c = conn()
    try:
        outro = _lead_por_variantes(lead["account_id"], variantes, exceto=lead_id)
        if not outro:
            resultado = ("ja_vinculado" if (lead.get("wa_id") or "") in variantes
                         and lead.get("wa_id") else "vinculado")
            if resultado == "vinculado":
                c.execute("UPDATE leads SET wa_id=? WHERE id=?", (wa_id, lead_id))
        elif e_so_wa(outro):
            _funde_so_wa_no_ig(c, outro, lead)
            # o wa_id que a Meta usa é o que o só-WA já tinha (veio do webhook)
            c.execute("UPDATE leads SET wa_id=? WHERE id=?", (outro["wa_id"] or wa_id, lead_id))
            encerradas = _uma_sessao_ativa(c, lead_id, sessao_atual)
            resultado = "fundido"
        else:
            resultado = "conflito"
        c.commit()
    except Exception:
        c.rollback()
        raise
    if resultado == "conflito":
        log_event("wa_conflito", lead["account_id"],
                  payload={"lead_id": lead_id, "dono": outro["id"]})
    if resultado == "fundido":
        for sid in encerradas:
            log_event("sessao_encerrada", lead["account_id"],
                      payload={"session_id": sid, "lead_id": lead_id, "motivo": "fusao_de_leads"})
    set_field(lead_id, "whatsapp", wa_id)
    return {"resultado": resultado, "lead_id": lead_id}


def abrir_janela(lead_id, canal: str) -> None:
    """A pessoa falou com a gente por este canal: 24h de resposta livre a partir de agora."""
    if canal not in CANAIS:
        return
    conn().execute(f"UPDATE leads SET {canal}_janela_ate=? WHERE id=?",
                   (in_seconds_iso(24 * 3600), lead_id))
    conn().commit()


def janela_aberta(lead: dict, canal: str) -> bool:
    if canal not in CANAIS or not lead:
        return False
    fim = lead.get(f"{canal}_janela_ate") or ""
    return bool(fim) and fim > now_iso()


def registrar_optin(lead_id, origem: str) -> None:
    """Primeiro opt-in vale: não troca a origem de quem já tinha consentido."""
    conn().execute(
        "UPDATE leads SET wa_optin_em=?, wa_optin_origem=? WHERE id=? AND COALESCE(wa_optin_em,'')=''",
        (now_iso(), origem, lead_id))
    conn().commit()


def registrar_optout(lead_id) -> None:
    conn().execute("UPDATE leads SET wa_optout_em=? WHERE id=?", (now_iso(), lead_id))
    conn().commit()


def limpar_optout(lead_id) -> None:
    conn().execute("UPDATE leads SET wa_optout_em='' WHERE id=?", (lead_id,))
    conn().commit()


# ---------- mensagens do WhatsApp (status) ----------

STATUS_WA = {"sent": "enviado", "delivered": "entregue", "read": "lido", "failed": "falhou"}
_ORDEM_STATUS = {"enviado": 1, "entregue": 2, "lido": 3}


def registrar_wa_msg(wamid, account_id, lead_id, origem, flow_name="", envio_id=None) -> None:
    if not wamid:
        return
    conn().execute(
        """INSERT OR IGNORE INTO wa_mensagens (wamid, account_id, lead_id, envio_id,
                                               flow_name, origem)
           VALUES (?,?,?,?,?,?)""",
        (str(wamid), account_id, lead_id, envio_id, flow_name or "", origem))
    conn().commit()


def aplicar_status_wa(wamid, status, categoria="", cobravel=False, erro_codigo=None):
    """Aplica o status que a Meta mandou. Devolve a linha (com `mudou`) ou None se o
    wamid não é nosso.

    A Meta reentrega webhook e manda `read` antes de `delivered` com frequência: o
    status só anda pra frente, e reentrega não conta de novo. `falhou` sempre aplica.
    """
    r = conn().execute("SELECT * FROM wa_mensagens WHERE wamid=?", (str(wamid),)).fetchone()
    if not r:
        return None
    linha = dict(r)
    novo = STATUS_WA.get(status, status)
    atual = linha.get("status") or "enviado"
    if novo == "falhou":
        mudou = atual != "falhou"
    else:
        mudou = _ORDEM_STATUS.get(novo, 0) > _ORDEM_STATUS.get(atual, 0) and atual != "falhou"
    sets, args = [], []
    if mudou:
        sets.append("status=?")
        args.append(novo)
    if categoria and not linha.get("categoria"):
        sets.append("categoria=?")
        args.append(categoria)
    if cobravel and not linha.get("cobravel"):
        sets.append("cobravel=1")
    if erro_codigo:
        sets.append("erro_codigo=?")
        args.append(int(erro_codigo))
    if sets:
        conn().execute(f"UPDATE wa_mensagens SET {', '.join(sets)} WHERE wamid=?",
                       args + [str(wamid)])
        conn().commit()
    linha = dict(conn().execute("SELECT * FROM wa_mensagens WHERE wamid=?",
                                (str(wamid),)).fetchone())
    linha["mudou"] = mudou
    if linha.get("envio_id"):
        aplicar_status_envio(linha["envio_id"], novo, categoria, cobravel, erro_codigo)
    return linha


# ---------- templates do WhatsApp ----------

def _template_row(r) -> dict:
    d = dict(r)
    d["componentes"] = json.loads(d.get("componentes") or "[]")
    return d


def salvar_templates(account_id, lista) -> int:
    """Upsert do que veio da Meta; o que não veio mais é apagado."""
    agora = now_iso()
    vistos = []
    for t in lista or []:
        nome, idioma = t.get("name") or "", t.get("language") or ""
        if not nome:
            continue
        vistos.append((nome, idioma))
        conn().execute(
            """INSERT INTO wa_templates (account_id, nome, idioma, categoria, status,
                                         componentes, sincronizado_em)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(account_id, nome, idioma) DO UPDATE SET
                 categoria=excluded.categoria, status=excluded.status,
                 componentes=excluded.componentes, sincronizado_em=excluded.sincronizado_em""",
            (account_id, nome, idioma, t.get("category") or "", t.get("status") or "",
             json.dumps(t.get("components") or [], ensure_ascii=False), agora))
    for r in conn().execute("SELECT id, nome, idioma FROM wa_templates WHERE account_id=?",
                            (account_id,)).fetchall():
        if (r["nome"], r["idioma"]) not in vistos:
            conn().execute("DELETE FROM wa_templates WHERE id=?", (r["id"],))
    conn().commit()
    return len(vistos)


def listar_templates(account_id, so_aprovados=False) -> list:
    q = "SELECT * FROM wa_templates WHERE account_id=?"
    if so_aprovados:
        q += " AND status='APPROVED'"
    return [_template_row(r) for r in conn().execute(q + " ORDER BY nome, idioma", (account_id,))]


def get_template(account_id, nome, idioma=None):
    q, args = "SELECT * FROM wa_templates WHERE account_id=? AND nome=?", [account_id, nome]
    if idioma:
        q += " AND idioma=?"
        args.append(idioma)
    r = conn().execute(q + " LIMIT 1", args).fetchone()
    return _template_row(r) if r else None


# ---------- transmissões ----------

def _filtro_publico(publico: dict, args: list) -> str:
    tipo = (publico or {}).get("tipo") or "todos"
    valor = (publico or {}).get("valor") or ""
    if tipo == "tag" and valor:
        args.append(valor)
        return " AND EXISTS (SELECT 1 FROM lead_tags t WHERE t.lead_id=l.id AND t.tag=?)"
    if tipo == "campo" and valor:
        campo_valor = (publico or {}).get("campo_valor") or ""
        if campo_valor:
            args += [valor, campo_valor]
            return (" AND EXISTS (SELECT 1 FROM lead_fields f WHERE f.lead_id=l.id "
                    "AND f.key=? AND f.value=?)")
        args.append(valor)
        return (" AND EXISTS (SELECT 1 FROM lead_fields f WHERE f.lead_id=l.id "
                "AND f.key=? AND TRIM(f.value)<>'')")
    return ""


def publico(account_id, publico: dict) -> list:
    """Quem pode receber: tem número, deu opt-in e não pediu pra sair."""
    args = [account_id]
    sql = ("SELECT l.* FROM leads l WHERE l.account_id=? AND COALESCE(l.wa_id,'')<>'' "
           "AND COALESCE(l.wa_optin_em,'')<>'' AND COALESCE(l.wa_optout_em,'')=''")
    sql += _filtro_publico(publico, args)
    return [dict(r) for r in conn().execute(sql + " ORDER BY l.id", args)]


def contar_publico(account_id, publico_: dict) -> int:
    args = [account_id]
    sql = ("SELECT COUNT(*) FROM leads l WHERE l.account_id=? AND COALESCE(l.wa_id,'')<>'' "
           "AND COALESCE(l.wa_optin_em,'')<>'' AND COALESCE(l.wa_optout_em,'')=''")
    sql += _filtro_publico(publico_, args)
    return conn().execute(sql, args).fetchone()[0]


def _transmissao_row(r) -> dict:
    d = dict(r)
    d["variaveis"] = json.loads(d.get("variaveis") or "{}")
    d["publico"] = json.loads(d.get("publico") or "{}")
    return d


def criar_transmissao(account_id, nome, template, idioma, categoria, variaveis, publico_,
                      agendada_para, ritmo_por_minuto, status="agendada") -> int:
    """`status='rascunho'` cria parada: o worker só olha agendada/enviando, então o
    rascunho não sai até alguém disparar (painel ou Claude, com confirmação)."""
    cur = conn().execute(
        """INSERT INTO transmissoes (account_id, nome, template, idioma, categoria, variaveis,
                                     publico, agendada_para, ritmo_por_minuto, criado_em, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (account_id, nome, template, idioma, (categoria or "").lower(),
         json.dumps(variaveis or {}, ensure_ascii=False),
         json.dumps(publico_ or {}, ensure_ascii=False), agendada_para or "",
         max(1, int(ritmo_por_minuto or 20)), now_iso(), status))
    conn().commit()
    return cur.lastrowid


def get_transmissao(transmissao_id):
    r = conn().execute("SELECT * FROM transmissoes WHERE id=?", (transmissao_id,)).fetchone()
    return _transmissao_row(r) if r else None


def listar_transmissoes(account_id) -> list:
    return [_transmissao_row(r) for r in conn().execute(
        "SELECT * FROM transmissoes WHERE account_id=? ORDER BY id DESC", (account_id,))]


def set_status_transmissao(transmissao_id, status) -> None:
    extra = ", concluido_em=?" if status in ("concluida", "cancelada") else ""
    args = [status] + ([now_iso()] if extra else []) + [transmissao_id]
    conn().execute(f"UPDATE transmissoes SET status=?{extra} WHERE id=?", args)
    conn().commit()


def aplicar_status_envio(envio_id, status_wa, categoria="", cobravel=False, erro_codigo=None):
    """Funil do destinatário. Cada coluna *_em só é preenchida uma vez (reentrega não
    conta de novo), e lido sem entregue antes conta como entregue: a Meta manda fora
    de ordem e quem leu recebeu."""
    agora = now_iso()
    sets, args = [], []
    if status_wa == "entregue":
        sets.append("entregue_em=CASE WHEN entregue_em='' THEN ? ELSE entregue_em END")
        args.append(agora)
    elif status_wa == "lido":
        sets += ["entregue_em=CASE WHEN entregue_em='' THEN ? ELSE entregue_em END",
                 "lido_em=CASE WHEN lido_em='' THEN ? ELSE lido_em END"]
        args += [agora, agora]
    elif status_wa == "falhou":
        sets += ["falhou_em=CASE WHEN falhou_em='' THEN ? ELSE falhou_em END", "status='falhou'"]
        args.append(agora)
    if categoria:
        sets.append("categoria=CASE WHEN categoria='' THEN ? ELSE categoria END")
        args.append(categoria)
    if cobravel:
        sets.append("cobravel=1")
    if erro_codigo:
        sets.append("erro_codigo=?")
        args.append(int(erro_codigo))
    if not sets:
        return
    conn().execute(f"UPDATE wa_envios SET {', '.join(sets)} WHERE id=?", args + [envio_id])
    conn().commit()


def marcar_respondido_wa(lead_id) -> None:
    """A pessoa escreveu no WA: conta como resposta do envio mais recente dela."""
    r = conn().execute(
        """SELECT id FROM wa_envios WHERE lead_id=? AND enviado_em<>'' AND enviado_em>=?
           AND respondido_em='' ORDER BY enviado_em DESC, id DESC LIMIT 1""",
        (lead_id, in_seconds_iso(-72 * 3600))).fetchone()
    if r:
        conn().execute("UPDATE wa_envios SET respondido_em=? WHERE id=?", (now_iso(), r["id"]))
        conn().commit()


def templates_enviados_24h(account_id) -> int:
    """Destinatários distintos de template nas últimas 24h. É conservador: a Meta só
    conta no limite quem estava fora da janela, aqui conta todo mundo."""
    return conn().execute(
        """SELECT COUNT(DISTINCT lead_id) FROM wa_mensagens WHERE account_id=?
           AND origem IN ('template','transmissao') AND ts>=?""",
        (account_id, in_seconds_iso(-24 * 3600))).fetchone()[0]


def leads_com_campo(account_id, chave) -> list:
    """Leads da conta com o campo `chave` preenchido, com o valor em `valor`."""
    return [dict(r) for r in conn().execute(
        """SELECT l.*, f.value AS valor FROM leads l JOIN lead_fields f ON f.lead_id=l.id
           WHERE l.account_id=? AND f.key=? AND TRIM(f.value)<>'' ORDER BY l.id""",
        (account_id, chave))]


# ---------- acesso do Claude (MCP) ----------

def _sha(valor: str) -> str:
    import hashlib
    return hashlib.sha256((valor or "").encode("utf-8")).hexdigest()


def mcp_guardar_token(token, tipo, cliente_id="", cliente_nome="", expira_em="") -> int:
    conn().execute("DELETE FROM mcp_tokens WHERE expira_em<>'' AND expira_em<=?", (now_iso(),))
    cur = conn().execute(
        """INSERT INTO mcp_tokens (hash, tipo, cliente_id, cliente_nome, final, expira_em)
           VALUES (?,?,?,?,?,?)""",
        (_sha(token), tipo, cliente_id, cliente_nome[:80], token[-4:], expira_em))
    conn().commit()
    return cur.lastrowid


def mcp_token(token, tipos=("manual", "acesso")):
    """Linha do token se ele existe, é de um dos `tipos` e não venceu.

    A busca é pelo hash (o índice UNIQUE), e o compare_digest no fim confirma em
    tempo constante: ninguém mede quantos caracteres acertou."""
    import hmac
    if not token or len(token) > 512:
        return None
    h = _sha(token)
    r = conn().execute("SELECT * FROM mcp_tokens WHERE hash=?", (h,)).fetchone()
    if not r or not hmac.compare_digest(r["hash"], h) or r["tipo"] not in tipos:
        return None
    if r["expira_em"] and r["expira_em"] <= now_iso():
        return None
    return dict(r)


def mcp_marcar_uso(token_id) -> None:
    conn().execute("UPDATE mcp_tokens SET ultimo_uso=? WHERE id=?", (now_iso(), token_id))
    conn().commit()


def mcp_apagar_token(token_id) -> None:
    conn().execute("DELETE FROM mcp_tokens WHERE id=?", (token_id,))
    conn().commit()


def mcp_apagar_tokens(tipos) -> int:
    cur = conn().execute(f"DELETE FROM mcp_tokens WHERE tipo IN {_em(list(tipos))}", list(tipos))
    conn().commit()
    return cur.rowcount


def mcp_apagar_do_cliente(cliente_id) -> None:
    conn().execute("DELETE FROM mcp_tokens WHERE cliente_id=? AND tipo<>'manual'", (cliente_id,))
    conn().commit()


def mcp_tokens_ativos() -> list:
    conn().execute("DELETE FROM mcp_tokens WHERE expira_em<>'' AND expira_em<=?", (now_iso(),))
    conn().commit()
    return [dict(r) for r in conn().execute(
        "SELECT id, tipo, cliente_id, cliente_nome, final, criado_em, expira_em, ultimo_uso "
        "FROM mcp_tokens ORDER BY id DESC")]


def mcp_registrar_cliente(client_id, nome, dados: dict) -> None:
    conn().execute("INSERT OR REPLACE INTO mcp_clientes (client_id, nome, dados) VALUES (?,?,?)",
                   (client_id, (nome or "")[:80], json.dumps(dados, ensure_ascii=False)))
    conn().commit()


def mcp_cliente(client_id):
    r = conn().execute("SELECT * FROM mcp_clientes WHERE client_id=?", (client_id or "",)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["dados"] = json.loads(d["dados"] or "{}")
    return d


def mcp_limpar_clientes_sem_uso(minutos=15) -> int:
    """Cliente registrado há mais de `minutos` que nunca recebeu token: registro
    abandonado (ou enchimento de propósito). Sai pra abrir vaga no teto."""
    cur = conn().execute(
        "DELETE FROM mcp_clientes WHERE criado_em < ? AND client_id NOT IN "
        "(SELECT cliente_id FROM mcp_tokens)", (in_seconds_iso(-minutos * 60),))
    conn().commit()
    return cur.rowcount


def mcp_contar_clientes() -> int:
    return conn().execute("SELECT COUNT(*) FROM mcp_clientes").fetchone()[0]


def mcp_guardar_codigo(codigo, dados: dict, expira_em) -> None:
    conn().execute("DELETE FROM mcp_codigos WHERE expira_em<=?", (now_iso(),))
    conn().execute("INSERT INTO mcp_codigos (hash, dados, expira_em) VALUES (?,?,?)",
                   (_sha(codigo), json.dumps(dados, ensure_ascii=False), expira_em))
    conn().commit()


def mcp_ler_codigo(codigo):
    r = conn().execute("SELECT * FROM mcp_codigos WHERE hash=?", (_sha(codigo),)).fetchone()
    if not r or r["expira_em"] <= now_iso():
        return None
    return json.loads(r["dados"])


def mcp_apagar_codigo(codigo) -> bool:
    """Uso único: quem apagar primeiro leva. Duas trocas simultâneas do mesmo código
    não geram dois tokens."""
    cur = conn().execute("DELETE FROM mcp_codigos WHERE hash=?", (_sha(codigo),))
    conn().commit()
    return cur.rowcount > 0
