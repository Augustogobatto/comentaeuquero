"""API do editor de fluxo. É o que o canvas Vue Flow consome.

Todas as rotas ficam sob /api e exigem a mesma sessão do painel. O formato do grafo
que entra e sai daqui é exatamente o que está gravado em flows.graph, que por sua
vez é o formato nativo do Vue Flow: nada de tradução no meio.

Import/export existe pra montar fluxo por script sem depender da UI.
"""
import csv
import io
import os
import re
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from . import db, instagram, runtime, whatsapp
from .senha import senha_definida


def exigir_sessao(request: Request):
    """Mesmo cookie do painel. A conta do Instagram e os fluxos ficam atrás dele.

    A sessão é uma linha em painel_sessions (token aleatório com validade), então
    revogar no painel derruba a API junto. Sem senha definida (nem ADMIN_PASSWORD
    no .env, nem a do primeiro acesso), a API fica fechada (não aberta).
    """
    if not senha_definida():
        raise HTTPException(403, "painel sem senha configurada")
    if not db.sessao_valida(request.cookies.get("ceq_session", "")):
        raise HTTPException(401, "faça login no painel")


router = APIRouter(prefix="/api", dependencies=[Depends(exigir_sessao)])


# ---------- levar embora ----------

@router.get("/backup.db")
def backup_db(request: Request):
    """Cópia consistente do banco inteiro, pro dono baixar e levar pra onde quiser.

    Usa a API de backup do SQLite (e não a cópia do arquivo), que respeita o WAL e
    escritas em andamento. O arquivo temporário some depois de enviado.
    """
    exigir_sessao(request)
    import sqlite3
    import tempfile
    tmp = tempfile.NamedTemporaryFile(prefix="ceq-backup-", suffix=".db", delete=False)
    tmp.close()
    try:
        dst = sqlite3.connect(tmp.name)
        try:
            db.conn().backup(dst)
            # sessão do painel não viaja: com o arquivo em mãos, quem pegasse o
            # backup entraria no painel com o cookie de quem baixou
            dst.execute("delete from painel_sessions")
            dst.commit()
        finally:
            dst.close()
        db.log_event("backup_baixado")
        return FileResponse(tmp.name, media_type="application/octet-stream",
                            filename="comentaeuquero-backup.db",
                            background=BackgroundTask(os.unlink, tmp.name))
    except BaseException:
        # deu errado antes de o FileResponse assumir o arquivo: não deixa cópia do
        # banco esquecida no /tmp
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


# ---------- validação ----------

TIPOS_VALIDOS = {
    "text", "buttons", "quick_replies", "media", "delay", "schedule",
    "wait_input", "condition", "action", "split", "webhook", "ai",
    "pedir_whatsapp", "template_wa",
}
TIPOS_QUE_RAMIFICAM = {"buttons", "quick_replies", "condition", "split", "wait_input", "webhook",
                       "pedir_whatsapp", "template_wa"}


def _so_tem_botao_de_link(node) -> bool:
    """True se é um nó de botões em que todo botão abre link (nenhum espera clique
    de volta). Esse tipo de nó pode ser o fim do fluxo sem problema nenhum."""
    if node.get("type") != "buttons":
        return False
    botoes = (node.get("data") or {}).get("buttons") or []
    return bool(botoes) and all(b.get("type") == "url" or b.get("url") for b in botoes)


def validar_grafo(graph: dict) -> list:
    """Problemas que fariam o fluxo se comportar mal em produção.

    Retorna lista de avisos legíveis. Grafo vazio é válido (fluxo em rascunho).
    """
    avisos = []
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    ids = [n.get("id") for n in nodes]

    if len(ids) != len(set(ids)):
        avisos.append("Tem nó com id repetido.")

    validos = set(ids)
    for n in nodes:
        tipo = n.get("type")
        data = n.get("data") or {}
        nome = f"nó '{n.get('id')}'"
        if tipo not in TIPOS_VALIDOS:
            avisos.append(f"{nome}: tipo desconhecido '{tipo}'.")
            continue
        if tipo == "text" and not (data.get("text") or "").strip():
            avisos.append(f"{nome}: mensagem de texto vazia.")
        variacoes = data.get("variants")
        if variacoes is not None:
            if not isinstance(variacoes, list):
                avisos.append(f"{nome}: as variações precisam ser uma lista de textos.")
            elif any(not (v or "").strip() for v in variacoes):
                avisos.append(f"{nome}: tem variação vazia — ela seria pulada no rodízio.")
        if tipo == "buttons":
            botoes = data.get("buttons") or []
            if not botoes:
                avisos.append(f"{nome}: nenhum botão configurado.")
            if len(botoes) > instagram.MAX_BUTTONS:
                avisos.append(f"{nome}: o Instagram aceita no máximo "
                              f"{instagram.MAX_BUTTONS} botões.")
            for b in botoes:
                if (b.get("type") == "url" or b.get("url")) and not b.get("url"):
                    avisos.append(f"{nome}: botão de link sem URL.")
        if tipo == "quick_replies":
            opcoes = data.get("options") or []
            if not opcoes:
                avisos.append(f"{nome}: nenhuma opção configurada.")
            if len(opcoes) > instagram.MAX_QUICK_REPLIES:
                avisos.append(f"{nome}: o Instagram aceita no máximo "
                              f"{instagram.MAX_QUICK_REPLIES} opções.")
        if tipo == "media" and not (data.get("url") or data.get("elements")):
            avisos.append(f"{nome}: mídia sem URL.")
        if tipo == "webhook" and not (data.get("url") or "").startswith("http"):
            avisos.append(f"{nome}: webhook sem URL válida.")
        if tipo == "template_wa" and not (data.get("template") or "").strip():
            avisos.append(f"{nome}: escolha o template do WhatsApp.")
        if tipo == "wait_input" and not (data.get("save_as") or "").strip():
            avisos.append(f"{nome}: falta dizer em qual campo salvar a resposta.")

    for e in edges:
        if e.get("source") not in validos or e.get("target") not in validos:
            avisos.append("Tem ligação apontando pra um nó que não existe.")
            break

    # nó que ramifica e não tem saída ligada deixa a pessoa parada pra sempre.
    # Exceção: botões que são todos de link não esperam resposta nenhuma, só abrem a
    # URL. Fluxo que termina num card com botão de link é legítimo (é o caso mais
    # comum de todos), então avisar ali seria só barulho.
    for n in nodes:
        if n.get("type") not in TIPOS_QUE_RAMIFICAM:
            continue
        if _so_tem_botao_de_link(n):
            continue
        if not any(e.get("source") == n.get("id") for e in edges):
            avisos.append(f"nó '{n.get('id')}': espera resposta mas não leva a lugar nenhum.")

    avisos.extend(_avisos_de_janela(nodes, edges))
    return avisos


def _avisos_de_janela(nodes, edges):
    """Soma os delays de cada caminho e avisa quando passam das 24h da Meta.

    Um delay longo demais não dá erro na hora de salvar: o fluxo só para de entregar
    naquele ponto, silenciosamente. Melhor avisar em quem monta.
    """
    por_id = {n.get("id"): n for n in nodes}
    saidas = {}
    for e in edges:
        saidas.setdefault(e.get("source"), []).append(e.get("target"))

    avisos, vistos = [], set()
    # Maior acumulado com que já entramos em cada nó. Chegar de novo com um valor
    # igual ou menor não descobre nada novo lá na frente, então para aí. Sem esse
    # corte, um fluxo com ciclo (menu de botões que volta ao próprio menu, por
    # exemplo) fazia a recursão andar por todos os caminhos até a profundidade 40:
    # medimos mais de 30 milhões de chamadas num grafo de 5 nós, o que segurava a
    # thread e travava tanto o salvar quanto o abrir do fluxo.
    maior_acumulado = {}

    def anda(node_id, acumulado, profundidade=0):
        if profundidade > 40 or node_id not in por_id:
            return
        if maior_acumulado.get(node_id, -1) >= acumulado:
            return
        maior_acumulado[node_id] = acumulado
        n = por_id[node_id]
        data = n.get("data") or {}
        if n.get("type") == "delay":
            acumulado += int(data.get("seconds") or 0) + int(data.get("minutes") or 0) * 60
            if acumulado > runtime.JANELA_S and node_id not in vistos:
                vistos.add(node_id)
                horas = acumulado / 3600
                avisos.append(
                    f"nó '{node_id}': a soma dos delays chega a {horas:.0f}h, além da "
                    f"janela de 24h do Instagram. As mensagens depois daqui não vão sair.")
        # quem espera resposta reabre a janela: zera a conta
        if n.get("type") in ("wait_input", "buttons", "quick_replies", "pedir_whatsapp",
                             "template_wa"):
            acumulado = 0
        for alvo in saidas.get(node_id, []):
            anda(alvo, acumulado, profundidade + 1)

    for n in nodes:
        if not any(e.get("target") == n.get("id") for e in edges):
            anda(n.get("id"), 0)
    return avisos


# ---------- posições ----------

def _tem_posicao(n) -> bool:
    pos = n.get("position")
    return (isinstance(pos, dict) and all(isinstance(pos.get(k), (int, float))
                                          and not isinstance(pos.get(k), bool) for k in ("x", "y")))


def posicionar(graph: dict, entry_node: str = "") -> dict:
    """Dá posição a nó que chegou sem (fluxo montado por script ou importado à mão).

    Sem `position` o canvas do editor quebrava ao abrir (lia position.x de undefined)
    e ficava mostrando o fluxo anterior. Layout simples, da esquerda pra direita:
    coluna = distância a partir da entrada seguindo as arestas, linha = ordem dentro
    da coluna. Nó que já tem posição fica onde está. Devolve o próprio grafo."""
    nodes = graph.get("nodes") or []
    faltando = [n for n in nodes if not _tem_posicao(n)]
    if not faltando:
        return graph
    ids = [n.get("id") for n in nodes]
    saidas = {}
    for e in graph.get("edges") or []:
        saidas.setdefault(e.get("source"), []).append(e.get("target"))
    alvos = {e.get("target") for e in graph.get("edges") or []}
    raizes = ([entry_node] if entry_node in ids else []) + [i for i in ids if i not in alvos]
    coluna = {}
    fila = [(r, 0) for r in raizes if r is not None]
    while fila:
        nid, c = fila.pop(0)
        if nid in coluna or nid not in ids:
            continue
        coluna[nid] = c
        fila += [(alvo, c + 1) for alvo in saidas.get(nid, [])]
    proxima = max(coluna.values(), default=-1) + 1
    linhas = {}
    for n in nodes:
        c = coluna.setdefault(n.get("id"), proxima)   # solto, sem ligação: vai pro fim
        linha = linhas.get(c, 0)
        linhas[c] = linha + 1
        if not _tem_posicao(n):
            n["position"] = {"x": 380 + c * 300, "y": 160 + linha * 180}
    return graph


# ---------- modelos ----------

class FlowIn(BaseModel):
    name: str | None = None
    graph: dict | None = None
    entry_node: str | None = None
    active: int | None = None


# wa_message: mensagem que chega no WhatsApp; wa_template_reply: clique num botão de
# template (as palavras-chave são o texto do botão)
TIPOS_GATILHO = ("comment", "live_comment", "story_reply", "dm", "wa_message",
                 "wa_template_reply")


class TriggerIn(BaseModel):
    type: str
    keywords: list[str] = []
    media_ids: list[str] = []
    public_reply: str = ""
    public_replies: list[str] = []
    active: int = 1


# ---------- rotas ----------

def _conta_ou_erro():
    conta = db.first_account()
    if not conta:
        raise HTTPException(400, "nenhuma conta do Instagram conectada")
    return conta


@router.get("/flows")
def listar_flows():
    conta = _conta_ou_erro()
    saida = []
    for f in db.list_flows(conta["id"]):
        gatilhos = db.list_triggers(f["id"])
        saida.append({
            "id": f["id"], "name": f["name"], "active": f["active"],
            "updated_at": f["updated_at"],
            "nos": len(f["graph"].get("nodes", [])),
            "triggers": gatilhos,
        })
    return saida


@router.post("/flows")
def criar_flow(body: FlowIn):
    conta = _conta_ou_erro()
    fid = db.create_flow(conta["id"], name=body.name or "Novo fluxo",
                         graph=body.graph, entry_node=body.entry_node or "",
                         active=1 if body.active is None else body.active)
    return {"id": fid}


@router.get("/flows/{flow_id}")
def ver_flow(flow_id: int):
    flow = db.get_flow(flow_id)
    if not flow:
        raise HTTPException(404, "fluxo não encontrado")
    flow["triggers"] = db.list_triggers(flow_id)
    flow["avisos"] = validar_grafo(flow["graph"])
    posicionar(flow["graph"], flow.get("entry_node") or "")
    return flow


@router.put("/flows/{flow_id}")
def salvar_flow(flow_id: int, body: FlowIn):
    if not db.get_flow(flow_id):
        raise HTTPException(404, "fluxo não encontrado")
    db.update_flow(flow_id, name=body.name, graph=body.graph,
                   entry_node=body.entry_node, active=body.active)
    flow = db.get_flow(flow_id)
    return {"ok": True, "avisos": validar_grafo(flow["graph"])}


@router.delete("/flows/{flow_id}")
def apagar_flow(flow_id: int):
    if not db.get_flow(flow_id):
        raise HTTPException(404, "fluxo não encontrado")
    db.delete_flow(flow_id)
    return {"ok": True}


@router.post("/flows/{flow_id}/triggers")
def criar_trigger(flow_id: int, body: TriggerIn):
    if not db.get_flow(flow_id):
        raise HTTPException(404, "fluxo não encontrado")
    if body.type not in TIPOS_GATILHO:
        raise HTTPException(400, f"tipo de gatilho inválido: {body.type}")
    tid = db.add_trigger(flow_id, body.type, keywords=body.keywords,
                         media_ids=body.media_ids, public_reply=body.public_reply,
                         public_replies=body.public_replies, active=body.active)
    return {"id": tid}


class TriggerPatch(BaseModel):
    active: int


@router.patch("/triggers/{trigger_id}")
def alternar_trigger(trigger_id: int, body: TriggerPatch):
    db.set_trigger_active(trigger_id, body.active)
    return {"ok": True, "active": 1 if body.active else 0}


@router.delete("/triggers/{trigger_id}")
def apagar_trigger(trigger_id: int):
    db.delete_trigger(trigger_id)
    return {"ok": True}


@router.get("/flows/{flow_id}/export")
def exportar(flow_id: int):
    """Fluxo inteiro num JSON que o import reconstrói. É o formato que uso pra montar
    fluxo por script."""
    flow = db.get_flow(flow_id)
    if not flow:
        raise HTTPException(404, "fluxo não encontrado")
    return {
        "ceq_flow": 1,
        "name": flow["name"],
        "entry_node": flow["entry_node"],
        "graph": flow["graph"],
        "triggers": [{k: t[k] for k in ("type", "keywords", "media_ids",
                                        "public_reply", "public_replies", "active")}
                     for t in db.list_triggers(flow_id)],
    }


@router.post("/flows/import")
def importar(body: dict):
    conta = _conta_ou_erro()
    if not isinstance(body.get("graph"), dict):
        raise HTTPException(400, "JSON sem 'graph'")
    avisos = validar_grafo(body["graph"])
    posicionar(body["graph"], body.get("entry_node") or "")
    fid = db.create_flow(conta["id"], name=body.get("name") or "Importado",
                         graph=body["graph"], entry_node=body.get("entry_node") or "",
                         active=0)   # entra desligado: quem importa revisa antes de ligar
    for t in body.get("triggers", []):
        db.add_trigger(fid, t.get("type", "comment"), keywords=t.get("keywords") or [],
                       media_ids=t.get("media_ids") or [],
                       public_reply=t.get("public_reply", ""),
                       public_replies=t.get("public_replies") or [],
                       active=t.get("active", 1))
    return {"id": fid, "avisos": avisos,
            "aviso_geral": "Fluxo importado desligado. Revise e ative quando quiser."}


@router.get("/medias")
def listar_medias():
    """Posts e Reels da conta, pro seletor de 'só neste post'."""
    conta = _conta_ou_erro()
    itens = instagram.fetch_media_list(conta["access_token"])
    return [{"id": m.get("id"), "caption": (m.get("caption") or "")[:80],
             "thumb": m.get("thumbnail_url") or m.get("media_url"),
             "permalink": m.get("permalink"), "type": m.get("media_type"),
             "timestamp": m.get("timestamp")} for m in itens]


@router.get("/flows/{flow_id}/metricas")
def metricas_do_flow(flow_id: int, periodo: str = "tudo"):
    """Funil de um fluxo só, pro editor. Devolve zeros se ainda não houve interação,
    em vez de vazio, pra tela mostrar o funil zerado em vez de sumir."""
    conta = _conta_ou_erro()
    flow = db.get_flow(flow_id)
    if not flow:
        raise HTTPException(404, "fluxo não encontrado")
    dias = {"7": 7, "30": 30}.get(periodo, 0)
    linhas = db.funil(conta["id"], dias=dias, flow_name=flow["name"])
    if linhas:
        return linhas[0]
    return {"fluxo": flow["name"], "existe": True, "acionaram": 0, "entregues": 0,
            "leram": 0, "avancaram": 0, "mensagens": 0}


# ---------- histórico ----------

RE_DIA = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Etapas do funil contadas por dia. `who` é o @ de quem interagiu: as colunas de
# PESSOA contam distintos, as de MENSAGEM contam linhas. Misturar as duas é o jeito
# mais fácil de fazer relatório que não bate com o painel.
COLUNAS_HISTORICO = """
    COUNT(DISTINCT CASE WHEN kind='fluxo_inicio' AND ok=1 AND who<>'' THEN who END) AS acionaram,
    SUM(kind='fluxo_inicio' AND ok=1) AS execucoes,
    SUM(kind='public_reply' AND ok=1) AS resposta_publica,
    COUNT(DISTINCT CASE WHEN kind='fluxo_envio' AND ok=1 AND who<>'' THEN who END) AS entregues,
    SUM(kind='fluxo_envio' AND ok=1) AS mensagens,
    COUNT(DISTINCT CASE WHEN kind='fluxo_lido' AND who<>'' THEN who END) AS leram,
    COUNT(DISTINCT CASE WHEN kind IN ('fluxo_postback','fluxo_quick_reply','fluxo_resposta')
                        AND ok=1 AND who<>'' THEN who END) AS avancaram,
    SUM(kind='sem_keyword') AS sem_keyword,
    SUM(ok=0) AS falhas,
    COUNT(*) AS eventos"""


def _fuso(tz: float) -> str:
    """Modificador do SQLite pra ler o ts, que é gravado em UTC, no fuso de quem olha.

    Sem isto o dia vira às 21h de Brasília e o pico da noite cai no dia seguinte —
    o relatório fica certo no total e errado em todos os dias."""
    if not -14 <= tz <= 14:
        raise HTTPException(400, "tz fora de -14..14")
    return "%+g hours" % tz


def _janela(desde: str, ate: str, fuso: str, args: list, col: str = "ts") -> str:
    """Recorte por DIA no fuso pedido, inclusive nas duas pontas.

    `col` é a coluna de data da tabela: events tem `ts`, leads tem `first_ts`."""
    sql = ""
    for valor, sinal in ((desde, ">="), (ate, "<=")):
        if not valor:
            continue
        if not RE_DIA.match(valor):
            raise HTTPException(400, f"data deve ser AAAA-MM-DD, veio '{valor}'")
        sql += f" AND date({col}, ?) {sinal} ?"
        args += [fuso, valor]
    return sql


def _eventos(conta_id, kind, desde, ate, fuso, flow, limit, offset, ordem="DESC"):
    sql = ("SELECT id, ts, kind, rule_keyword, source, ok, who, payload FROM events "
           "WHERE (account_id=? OR account_id IS NULL)")
    args = [conta_id]
    if kind:
        kinds = [k.strip() for k in kind.split(",") if k.strip()]
        sql += " AND kind IN (%s)" % ",".join("?" * len(kinds))
        args += kinds
    sql += _janela(desde, ate, fuso, args)
    if flow:
        sql += " AND rule_keyword=?"
        args.append(flow)
    sql += f" ORDER BY id {ordem} LIMIT ? OFFSET ?"
    args += [max(1, min(limit, 50000)), max(0, offset)]
    return db.conn().execute(sql, args)


@router.get("/eventos")
def listar_eventos(limit: int = 40, kind: str = "", desde: str = "", ate: str = "",
                   flow: str = "", offset: int = 0, tz: float = -3):
    """Últimos eventos com o payload inteiro, que é onde fica a resposta da Meta.

    Sem isto, depurar uma instância que não é a sua exige entrar no servidor e abrir
    o SQLite na mão. O painel mostra o resumo bonito; aqui é o cru.

    `desde`/`ate` recortam por dia no fuso `tz` (padrão Brasília) e `offset` pagina,
    porque sem os dois só dava pra ver as últimas horas de uma instância movimentada.
    """
    conta = _conta_ou_erro()
    return [dict(r) for r in _eventos(conta["id"], kind, desde, ate, _fuso(tz), flow,
                                      limit, offset)]


@router.get("/historico")
def historico(desde: str = "", ate: str = "", tz: float = -3, por: str = "dia",
              flow: str = ""):
    """O funil dia a dia — é o relatório que antes só existia entrando no servidor.

    `por`: dia, fluxo, dia_fluxo ou total (uma linha só, pessoas distintas no
    período inteiro: somar os dias contaria duas vezes quem voltou). Dia sem evento
    nenhum não vira linha.
    """
    conta = _conta_ou_erro()
    colunas = {"dia": "date(ts, ?) AS dia",
               "fluxo": "COALESCE(NULLIF(rule_keyword,''),'(sem fluxo)') AS fluxo"}
    chaves = {"dia": ["dia"], "fluxo": ["fluxo"],
              "dia_fluxo": ["dia", "fluxo"], "total": []}.get(por)
    if chaves is None:
        raise HTTPException(400, "por deve ser dia, fluxo, dia_fluxo ou total")
    fuso = _fuso(tz)
    args = [fuso] if "dia" in chaves else []
    sql = ("SELECT " + "".join(colunas[k] + "," for k in chaves) + COLUNAS_HISTORICO +
           " FROM events WHERE (account_id=? OR account_id IS NULL)")
    args.append(conta["id"])
    sql += _janela(desde, ate, fuso, args)
    if flow:
        sql += " AND rule_keyword=?"
        args.append(flow)
    grupo = ", ".join(str(i + 1) for i in range(len(chaves)))
    if grupo:
        sql += f" GROUP BY {grupo} ORDER BY {grupo}"
    saida = []
    for r in db.conn().execute(sql, args):
        linha = dict(r)
        for k, v in linha.items():
            if v is None and k not in chaves:
                linha[k] = 0
        saida.append(linha)
    return saida


@router.get("/campos")
def campos_capturados(desde: str = "", ate: str = "", tz: float = -3):
    """Quantos leads preencheram cada campo que os fluxos pedem (nome, e-mail...).

    É a pergunta "quantos viraram lead de verdade": o disparo do fluxo conta quem
    comentou, este conta quem chegou a entregar o dado. `preencheram_tudo` cruza
    nome com e-mail, que é o par que costuma valer como cadastro.
    """
    conta = _conta_ou_erro()
    fuso = _fuso(tz)
    args = [conta["id"]]
    onde = _janela(desde, ate, fuso, args, col="l.first_ts")
    total = db.conn().execute(
        f"SELECT COUNT(*) FROM leads l WHERE l.account_id=?{onde}", args).fetchone()[0]
    args2 = [conta["id"]]
    onde2 = _janela(desde, ate, fuso, args2, col="l.first_ts")
    por_campo = [{"campo": r["key"], "leads": r["n"]} for r in db.conn().execute(
        f"""SELECT f.key, COUNT(DISTINCT f.lead_id) n FROM lead_fields f
            JOIN leads l ON l.id = f.lead_id
            WHERE l.account_id=? AND TRIM(f.value) <> ''{onde2}
            GROUP BY f.key ORDER BY n DESC""", args2)]
    args3 = [conta["id"]]
    onde3 = _janela(desde, ate, fuso, args3, col="l.first_ts")
    completos = db.conn().execute(
        f"""SELECT COUNT(*) FROM leads l WHERE l.account_id=?{onde3}
            AND EXISTS (SELECT 1 FROM lead_fields f WHERE f.lead_id=l.id
                        AND f.key IN ('nome','name') AND TRIM(f.value)<>'')
            AND EXISTS (SELECT 1 FROM lead_fields f WHERE f.lead_id=l.id
                        AND f.key IN ('email','e-mail','mail') AND TRIM(f.value)<>'')""",
        args3).fetchone()[0]
    return {"leads_no_periodo": total, "preencheram_nome_e_email": completos,
            "por_campo": por_campo}


@router.get("/leads")
def listar_leads(desde: str = "", ate: str = "", tz: float = -3, campo: str = "",
                 keyword: str = "", limit: int = 200, offset: int = 0):
    """Os leads do período com os campos que eles preencheram no fluxo.

    `campo` filtra quem tem aquele campo preenchido (ex.: campo=email). A data
    olha o first_ts, que é quando a pessoa apareceu pela primeira vez.
    """
    conta = _conta_ou_erro()
    fuso = _fuso(tz)
    args = [conta["id"]]
    sql = ("SELECT l.id, l.username, l.name, l.followers, l.is_follower, l.first_ts, "
           "l.last_ts, l.interactions, l.last_keyword FROM leads l WHERE l.account_id=?")
    sql += _janela(desde, ate, fuso, args, col="l.first_ts")
    if keyword:
        sql += " AND l.last_keyword=?"
        args.append(keyword)
    if campo:
        sql += (" AND EXISTS (SELECT 1 FROM lead_fields f WHERE f.lead_id=l.id "
                "AND f.key=? AND TRIM(f.value)<>'')")
        args.append(campo)
    sql += " ORDER BY l.first_ts DESC LIMIT ? OFFSET ?"
    args += [max(1, min(limit, 50000)), max(0, offset)]
    linhas = [dict(r) for r in db.conn().execute(sql, args)]
    for l in linhas:
        l["campos"] = db.lead_fields(l["id"])
    return linhas


_INICIO_DE_FORMULA = ("=", "+", "-", "@", "\t", "\r")
_SO_NUMERO = re.compile(r"^[+-][\d\s().-]*$")


def _celula(valor):
    """Valor seguro pra planilha. Nome do Instagram e resposta de lead são texto
    livre de terceiros: começando com "=" (ou +, -, @), Excel e Google Sheets
    executam como fórmula ao abrir o arquivo. O apóstrofo na frente faz a planilha
    tratar como texto, e ela não mostra o apóstrofo."""
    if not isinstance(valor, str) or not valor.startswith(_INICIO_DE_FORMULA):
        return valor
    # telefone com +55 e número negativo continuam crus: só dígito e pontuação de
    # telefone não formam fórmula, e o apóstrofo atrapalharia quem importa o CSV
    if _SO_NUMERO.match(valor):
        return valor
    return "'" + valor


class _EscritorSeguro:
    """csv.writer que passa toda célula pelo _celula."""

    def __init__(self, w):
        self._w = w

    def writerow(self, linha):
        self._w.writerow([_celula(v) for v in linha])


@router.get("/export.csv")
def exportar_csv(tipo: str = "historico", desde: str = "", ate: str = "", tz: float = -3,
                 por: str = "dia", kind: str = "", flow: str = "", limit: int = 50000,
                 sep: str = ","):
    """O mesmo dado do /historico e do /eventos, em CSV, pra conferir na planilha.

    tipo: historico (uma linha por dia), execucoes (uma linha por disparo de fluxo)
    ou eventos (tudo, com payload). Vai com BOM porque senão o Excel come o acento.
    """
    if sep not in (",", ";", "\t"):
        raise HTTPException(400, "sep deve ser , ou ; ou tab")
    conta = _conta_ou_erro()
    fuso = _fuso(tz)
    buf = io.StringIO()
    buf.write("﻿")
    w = _EscritorSeguro(csv.writer(buf, delimiter=sep, lineterminator="\n"))

    if tipo == "historico":
        linhas = historico(desde=desde, ate=ate, tz=tz, por=por, flow=flow)
        cabecalho = list(linhas[0].keys()) if linhas else ["dia"]
        w.writerow(cabecalho)
        for l in linhas:
            w.writerow([l.get(c, "") for c in cabecalho])
    elif tipo == "leads":
        linhas = listar_leads(desde=desde, ate=ate, tz=tz, campo=flow, limit=limit)
        chaves = sorted({k for l in linhas for k in l["campos"]})
        fixas = ["username", "name", "first_ts", "last_ts", "last_keyword",
                 "followers", "is_follower", "interactions"]
        w.writerow(fixas + chaves)
        for l in linhas:
            w.writerow([l.get(c, "") for c in fixas] + [l["campos"].get(k, "") for k in chaves])
    elif tipo in ("execucoes", "eventos"):
        so_inicio = tipo == "execucoes"
        cru = _eventos(conta["id"], "fluxo_inicio" if so_inicio else kind, desde, ate,
                       fuso, flow, limit, 0, ordem="ASC")
        if so_inicio:
            w.writerow(["dia", "hora_local", "ts_utc", "username", "origem", "fluxo", "ok"])
        else:
            w.writerow(["id", "dia", "hora_local", "ts_utc", "kind", "fluxo", "origem",
                        "ok", "username", "payload"])
        for r in cru:
            local = db.conn().execute("SELECT datetime(?, ?)", (r["ts"], fuso)).fetchone()[0] or ""
            dia, _, hora = local.partition(" ")
            if so_inicio:
                w.writerow([dia, hora, r["ts"], r["who"], r["source"], r["rule_keyword"], r["ok"]])
            else:
                w.writerow([r["id"], dia, hora, r["ts"], r["kind"], r["rule_keyword"],
                            r["source"], r["ok"], r["who"], r["payload"]])
    else:
        raise HTTPException(400, "tipo deve ser historico, leads, execucoes ou eventos")

    nome = f"ceq_{tipo}_{desde or 'inicio'}_{ate or 'hoje'}.csv"
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@router.get("/tags")
def listar_tags():
    conta = _conta_ou_erro()
    return [{"tag": t, "leads": n} for t, n in db.all_tags(conta["id"])]


@router.get("/sessoes")
def listar_sessoes(limit: int = 50):
    """Quem está parado em qual nó agora. É o raio-x do motor pra depurar fluxo."""
    conta = _conta_ou_erro()
    linhas = db.conn().execute(
        """SELECT s.id, s.status, s.node_id, s.waiting_for, s.updated_at,
                  f.name AS fluxo, l.username, l.igsid
           FROM flow_sessions s
           JOIN flows f ON f.id = s.flow_id
           JOIN leads l ON l.id = s.lead_id
           WHERE s.account_id=? ORDER BY s.id DESC LIMIT ?""",
        (conta["id"], limit))
    return [dict(r) for r in linhas]


# ---------- WhatsApp: templates ----------

RE_VARIAVEL = re.compile(r"\{\{\s*(\d+)\s*\}\}")
RE_NOME_TEMPLATE = re.compile(r"^[a-z0-9_]{1,512}$")
CATEGORIAS_TEMPLATE = {"MARKETING", "UTILITY"}


def _componentes(tpl) -> list:
    return (tpl or {}).get("componentes") or (tpl or {}).get("components") or []


def corpo_do_template(tpl) -> str:
    for c in _componentes(tpl):
        if str(c.get("type", "")).upper() == "BODY":
            return c.get("text") or ""
    return ""


def variaveis_do_template(tpl) -> list:
    """["1","2"] a partir dos {{n}} do corpo, em ordem numérica e sem repetir."""
    nums = sorted({int(n) for n in RE_VARIAVEL.findall(corpo_do_template(tpl))})
    return [str(n) for n in nums]


def botoes_do_template(tpl) -> list:
    saida = []
    for c in _componentes(tpl):
        if str(c.get("type", "")).upper() == "BUTTONS":
            saida += [b.get("text", "") for b in c.get("buttons") or []
                      if str(b.get("type", "")).upper() == "QUICK_REPLY"]
    return saida


def _conta_wa_ou_erro():
    conta = _conta_ou_erro()
    if not whatsapp.configurado(conta):
        raise HTTPException(400, "WhatsApp não configurado")
    return conta


def eh_amostra(nome) -> bool:
    """Templates de exemplo que a Meta cria em toda conta nova (sample_* em 4 idiomas
    e hello_world). Ninguém manda isso pra lead; a lista esconde por padrão."""
    return (nome or "").startswith("sample_") or nome == "hello_world"


def _template_publico(t) -> dict:
    return {"nome": t["nome"], "idioma": t["idioma"], "categoria": t["categoria"],
            "status": t["status"], "corpo": corpo_do_template(t),
            "variaveis": variaveis_do_template(t), "botoes": botoes_do_template(t),
            "pasta_id": t.get("pasta_id"), "pasta": t.get("pasta") or "",
            "amostra": eh_amostra(t["nome"])}


def sincronizar_templates(conta):
    """Total sincronizado, ou None se a Meta falhou (aí nada local é apagado)."""
    lista = whatsapp.list_templates(conta)
    if lista is None:
        return None
    return db.salvar_templates(conta["id"], lista)


AUTOSYNC_INTERVALO = 60  # segundos entre sincronizações automáticas


def sincronizar_se_pendente(conta) -> bool:
    """Template criado aqui nasce PENDING e só vira APPROVED no banco depois de um
    sync. Quem abre Templates ou Nova transmissão com algo em análise ganha um sync
    antes, no máximo um a cada AUTOSYNC_INTERVALO (recarregar a página não martela a
    Meta). O relógio anda mesmo se a Meta falhar. True se sincronizou."""
    if not db.tem_template_pendente(conta["id"]):
        return False
    chave = f"wa_tpl_autosync:{conta['id']}"
    agora = time.time()
    try:
        ultimo = float(db.get_ajuste(chave, "0"))
    except ValueError:
        ultimo = 0.0
    if agora - ultimo < AUTOSYNC_INTERVALO:
        return False
    db.set_ajuste(chave, agora)
    total = sincronizar_templates(conta)
    db.log_event("wa_templates_sync", conta["id"], ok=total is not None,
                 payload={"total": total, "auto": True})
    return total is not None


@router.get("/wa/templates")
def wa_templates(aprovados: int = 0):
    conta = db.first_account()
    if not whatsapp.configurado(conta):
        return []
    return [_template_publico(t) for t in db.listar_templates(conta["id"], bool(aprovados))]


@router.post("/wa/templates/sync")
def wa_templates_sync():
    conta = _conta_wa_ou_erro()
    total = sincronizar_templates(conta)
    db.log_event("wa_templates_sync", conta["id"], ok=total is not None, payload={"total": total})
    if total is None:
        raise HTTPException(502, "a Meta não respondeu; os templates salvos foram mantidos")
    return {"total": total}


# ---------- WhatsApp: pastas de template (só do CEQ, a Meta não tem) ----------

class PastaIn(BaseModel):
    nome: str


def _nome_pasta(nome) -> str:
    nome = " ".join((nome or "").split())
    if not nome:
        raise HTTPException(400, "dê um nome pra pasta")
    if len(nome) > 60:
        raise HTTPException(400, "nome de pasta com até 60 caracteres")
    return nome


@router.get("/wa/pastas")
def wa_pastas():
    conta = _conta_wa_ou_erro()
    return db.listar_pastas(conta["id"])


@router.post("/wa/pastas")
def wa_pasta_criar(body: PastaIn):
    conta = _conta_wa_ou_erro()
    nome = _nome_pasta(body.nome)
    pid = db.criar_pasta(conta["id"], nome)
    if pid is None:
        raise HTTPException(409, "já existe uma pasta com esse nome")
    return {"id": pid, "nome": nome}


@router.patch("/wa/pastas/{pasta_id}")
def wa_pasta_renomear(pasta_id: int, body: PastaIn):
    conta = _conta_wa_ou_erro()
    if not db.get_pasta(conta["id"], pasta_id):
        raise HTTPException(404, "pasta não encontrada")
    nome = _nome_pasta(body.nome)
    if not db.renomear_pasta(conta["id"], pasta_id, nome):
        raise HTTPException(409, "já existe uma pasta com esse nome")
    return {"id": pasta_id, "nome": nome}


@router.delete("/wa/pastas/{pasta_id}")
def wa_pasta_apagar(pasta_id: int):
    conta = _conta_wa_ou_erro()
    if not db.apagar_pasta(conta["id"], pasta_id):
        raise HTTPException(404, "pasta não encontrada")
    return {"ok": True}


class MoverIn(BaseModel):
    nome: str
    idioma: str
    pasta_id: int | None = None


@router.put("/wa/templates/pasta")
def wa_template_mover(body: MoverIn):
    conta = _conta_wa_ou_erro()
    if body.pasta_id is not None and not db.get_pasta(conta["id"], body.pasta_id):
        raise HTTPException(404, "pasta não encontrada")
    if not db.mover_template(conta["id"], body.nome, body.idioma, body.pasta_id):
        raise HTTPException(404, "template não encontrado")
    return {"ok": True}


class TemplateIn(BaseModel):
    nome: str
    idioma: str = "pt_BR"
    categoria: str
    corpo: str
    exemplos: list[str] = []
    botoes: list[str] = []


@router.post("/wa/templates")
def wa_template_criar(body: TemplateIn):
    conta = _conta_wa_ou_erro()
    if not RE_NOME_TEMPLATE.match(body.nome or ""):
        raise HTTPException(400, "nome só com letras minúsculas, números e _ (ex.: boas_vindas)")
    categoria = (body.categoria or "").upper()
    if categoria not in CATEGORIAS_TEMPLATE:
        raise HTTPException(400, "categoria deve ser MARKETING ou UTILITY")
    if not (body.corpo or "").strip():
        raise HTTPException(400, "o corpo do template está vazio")
    variaveis = variaveis_do_template({"components": [{"type": "BODY", "text": body.corpo}]})
    exemplos = [e for e in body.exemplos if (e or "").strip()]
    if len(exemplos) != len(variaveis):
        # a Meta recusa template com variável sem exemplo; melhor dizer aqui
        raise HTTPException(400, f"o corpo tem {len(variaveis)} variável(is) e vieram "
                                 f"{len(exemplos)} exemplo(s): um por variável")
    botoes = [b.strip() for b in body.botoes if (b or "").strip()]
    if len(botoes) > 3:
        raise HTTPException(400, "até 3 botões")
    ok, resposta = whatsapp.create_template(conta, body.nome, body.idioma or "pt_BR",
                                            categoria, body.corpo, exemplos, botoes)
    db.log_event("wa_template_criado", conta["id"], ok=ok,
                 payload={"nome": body.nome, "status": resposta.get("status", "")})
    if not ok:
        msg = (resposta.get("error") or {}).get("message") or "a Meta recusou o template"
        raise HTTPException(400, instagram.sem_segredo(msg)[:300])
    sincronizar_templates(conta)
    return {"ok": True, "status": resposta.get("status", "")}


# ---------- WhatsApp: público das transmissões ----------

@router.get("/wa/publico")
def wa_publico(tipo: str = "todos", valor: str = "", campo_valor: str = ""):
    """Contagem ao vivo do público, pro formulário de transmissão."""
    conta = _conta_wa_ou_erro()
    return {"total": db.contar_publico(conta["id"], {"tipo": tipo, "valor": valor,
                                                     "campo_valor": campo_valor})}


@router.get("/wa/estado")
def wa_estado_api():
    """O editor pergunta isto pra decidir se mostra gatilhos e passos de WhatsApp."""
    from .main import wa_estado
    return wa_estado(db.first_account())
