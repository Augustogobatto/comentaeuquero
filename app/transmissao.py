"""Transmissões do WhatsApp: fila com ritmo, teto diário e relatório.

Tocada pelo mesmo worker do motor (runtime.tick), uma rodada a cada poucos segundos.
Cada rodada manda no máximo o que o ritmo da transmissão permite desde a última, e
para quando:
  - a Meta mandou esperar (cooldown do WhatsApp): o destinatário fica `pendente`,
    nunca `falhou`, e a fila retoma sozinha quando o freio solta;
  - o teto diário do número estourou: espera o dia andar;
  - acabou a fila: a transmissão vira `concluida`.

O lead é relido na hora de enviar: quem pediu SAIR depois do agendamento é pulado.

Cada envio vira `enviando` (gravado) ANTES de chamar a Meta. Se o processo cair ou o
banco falhar entre o 200 da Meta e a gravação do `enviado`, o destinatário fica em
`enviando`; a rodada seguinte manda ele pra `revisar` em vez de reenviar: template
duplicado é cobrado duas vezes e chega duas vezes.
"""
import time

from . import db, whatsapp

# Brasil, por mensagem, em USD (tabela da Meta). Sobrescrevível por ajuste, porque a
# Meta muda o preço e não avisa o app. É sempre exibido como estimativa.
PRECOS_PADRAO_USD = {"marketing": 0.0625, "utility": 0.0068, "authentication": 0.0068}

# Erros da Meta que mais aparecem numa transmissão, em português e com o que fazer.
# O código continua visível ao lado: é ele que o suporte da Meta pede.
ERROS_META = {
    131042: ("A conta do WhatsApp está sem forma de pagamento (ou o pagamento falhou).",
             "Cadastre um cartão no Gerenciador do WhatsApp, em Cobrança, e dispare de novo."),
    131047: ("A pessoa está fora da janela de 24h e a mensagem não era template.",
             "Fora da janela só sai template aprovado."),
    131026: ("O número não recebe esta mensagem: não tem WhatsApp, está com app antigo ou "
             "não aceitou os termos novos.",
             "Nada a fazer daqui; confira se o número está certo."),
    131049: ("A Meta segurou a mensagem de marketing pra essa pessoa (ela já recebeu muito "
             "marketing de várias empresas).",
             "Não reenvie em seguida; tente outro dia ou com template de utilidade, se couber."),
    131050: ("A pessoa pediu pra não receber marketing desta empresa.",
             "Ela fica fora das próximas transmissões de marketing."),
    132000: ("O número de variáveis enviado não bate com o template.",
             "Confira os valores de {{1}}, {{2}}... da transmissão."),
    132001: ("O template não existe na Meta com esse nome e idioma.",
             "Sincronize os templates e confira se ele ainda está aprovado."),
    131056: ("Muitas mensagens pro mesmo número em pouco tempo.",
             "O CEQ adia esse envio sozinho; se persistir, diminua o ritmo."),
    130472: ("O número está num experimento da Meta que não entrega marketing pra ele.",
             "Nada a fazer; a Meta não cobra essa mensagem."),
    368: ("A conta do WhatsApp está bloqueada ou restrita pela Meta.",
          "Veja a qualidade e os avisos no Gerenciador do WhatsApp antes de disparar de novo."),
    131031: ("A conta do WhatsApp está bloqueada ou restrita pela Meta.",
             "Veja a qualidade e os avisos no Gerenciador do WhatsApp antes de disparar de novo."),
}


def explicar_erro(codigo) -> dict:
    texto, fazer = ERROS_META.get(int(codigo), ("Erro da Meta sem explicação conhecida.",
                                                "Procure o código na documentação da Cloud API."))
    return {"codigo": int(codigo), "texto": texto, "fazer": fazer}


# 131056 (par remetente-destinatário saturado) é do destinatário, não do número: ele
# é adiado e a fila segue. Espera cresce a cada vez; passou do teto, vira falha.
ADIAMENTO_BASE_S = 60
MAX_ADIAMENTOS = 5


def preco(categoria: str) -> float:
    cat = (categoria or "").lower()
    salvo = db.get_ajuste(f"wa_preco_{cat}")
    try:
        return float(salvo) if salvo else PRECOS_PADRAO_USD.get(cat, PRECOS_PADRAO_USD["marketing"])
    except ValueError:
        return PRECOS_PADRAO_USD.get(cat, PRECOS_PADRAO_USD["marketing"])


def limite_diario(account):
    """Quantos destinatários de template por 24h. None = ilimitado."""
    salvo = db.get_ajuste("wa_limite_diario")
    if str(salvo).isdigit():
        return int(salvo)
    return (account or {}).get("wa_limite")


def _materializa(t) -> None:
    """Fotografa o público no momento de começar: quem entrar depois na etiqueta não
    recebe esta transmissão (é o que o dono viu na contagem ao agendar)."""
    for lead in db.publico(t["account_id"], t["publico"]):
        db.conn().execute(
            "INSERT OR IGNORE INTO wa_envios (transmissao_id, lead_id, wa_id) VALUES (?,?,?)",
            (t["id"], lead["id"], lead["wa_id"]))
    db.conn().execute("UPDATE transmissoes SET status='enviando', iniciado_em=? WHERE id=?",
                      (db.now_iso(), t["id"]))
    db.conn().commit()


def _proximo_pendente(transmissao_id, agora: float):
    """Próximo pendente que já pode sair. Devolve (envio, ha_adiados)."""
    r = db.conn().execute(
        "SELECT * FROM wa_envios WHERE transmissao_id=? AND status='pendente' "
        "AND COALESCE(adiar_ate,0)<=? ORDER BY id LIMIT 1", (transmissao_id, agora)).fetchone()
    if r:
        return dict(r), False
    adiado = db.conn().execute(
        "SELECT 1 FROM wa_envios WHERE transmissao_id=? AND status='pendente' LIMIT 1",
        (transmissao_id,)).fetchone()
    return None, bool(adiado)


def _marca(envio_id, **campos) -> None:
    sets = ", ".join(f"{k}=?" for k in campos)
    db.conn().execute(f"UPDATE wa_envios SET {sets} WHERE id=?", list(campos.values()) + [envio_id])
    db.conn().commit()


def _enviando_orfaos_pra_revisar(transmissao_id) -> int:
    """`enviando` no começo da rodada é sobra de uma rodada que quebrou no meio: não
    dá pra saber se a Meta entregou, então não reenvia."""
    cur = db.conn().execute(
        "UPDATE wa_envios SET status='revisar', erro=? WHERE transmissao_id=? AND status='enviando'",
        ("interrompido durante o envio: confira antes de reenviar", transmissao_id))
    db.conn().commit()
    return cur.rowcount


def _avisa_teto(t) -> None:
    """Um aviso por transmissão por dia, não um por rodada do worker."""
    chave = f"wa_teto_aviso:{t['id']}"
    hoje = db.now_iso()[:10]
    if db.get_ajuste(chave) == hoje:
        return
    db.set_ajuste(chave, hoje)
    db.log_event("wa_teto_diario", t["account_id"], t["nome"], "transmissao",
                 payload={"transmissao_id": t["id"]})


def _toca(t, agora: float) -> int:
    from .runtime import render   # import tardio: runtime importa este módulo no tick
    conta = db.get_account(t["account_id"])
    if not whatsapp.configurado(conta):
        return 0
    tentou = 0
    _enviando_orfaos_pra_revisar(t["id"])
    proximo_em = float(t.get("proximo_em") or 0)
    intervalo = 60.0 / max(1, int(t.get("ritmo_por_minuto") or 20))
    teto = limite_diario(conta)
    # Relógio do ritmo: cada envio empurra o próximo em `intervalo`, e numa mesma
    # rodada saem todos os que já venceram (o worker roda a cada ~5s; um envio por
    # rodada travaria tudo em 12/min). Relógio parado há mais de uma rodada (início,
    # pausa, worker fora do ar) recomeça de agora, sem rajada pra "recuperar".
    if proximo_em < agora - 5:
        proximo_em = agora
    while agora >= proximo_em:
        envio, ha_adiados = _proximo_pendente(t["id"], agora)
        if not envio:
            if not ha_adiados:
                db.set_status_transmissao(t["id"], "concluida")
            break
        if whatsapp.cooldown_restante() > 0:
            break
        if teto is not None and db.templates_enviados_24h(t["account_id"]) >= teto:
            _avisa_teto(t)
            break
        lead = db.get_lead(envio["lead_id"]) if envio.get("lead_id") else None
        if not lead or not lead.get("wa_id") or lead.get("wa_optout_em"):
            _marca(envio["id"], status="pulado", erro="optout" if lead else "lead apagado")
            continue
        variaveis = t.get("variaveis") or {}
        numeros = sorted(int(k) for k in variaveis if str(k).isdigit())
        params = [render(variaveis.get(str(i), ""), lead, {})
                  for i in range(1, (numeros[-1] if numeros else 0) + 1)]
        _marca(envio["id"], status="enviando", wa_id=lead["wa_id"])
        ok, _, body = whatsapp.send_template(conta, lead["wa_id"], t["template"],
                                             t.get("idioma") or "pt_BR", params)
        tentou += 1
        codigo = whatsapp.codigo_erro(body)
        if ok is None and codigo not in whatsapp.CODIGOS_RETENTAR:
            _marca(envio["id"], status="pendente")
            break   # freio da Meta: fica pendente, a fila inteira tenta na próxima
        if ok is None:
            # par saturado: adia só este destinatário e segue com o resto da fila
            n = int(envio.get("adiamentos") or 0) + 1
            if n > MAX_ADIAMENTOS:
                _marca(envio["id"], status="falhou", falhou_em=db.now_iso(),
                       erro_codigo=codigo, erro="destinatário saturado (131056)")
            else:
                _marca(envio["id"], status="pendente", adiamentos=n,
                       adiar_ate=agora + ADIAMENTO_BASE_S * (2 ** (n - 1)))
        elif ok:
            wamid = whatsapp.wamid_de(body)
            _marca(envio["id"], status="enviado", wamid=wamid, enviado_em=db.now_iso())
            db.registrar_wa_msg(wamid, t["account_id"], lead["id"], "transmissao",
                                t["nome"], envio_id=envio["id"])
        else:
            erro = ((body.get("error") or {}).get("message", "") if isinstance(body, dict)
                    else str(body))[:200]
            _marca(envio["id"], status="falhou", falhou_em=db.now_iso(),
                   erro_codigo=codigo or None, erro=erro)
            if codigo == whatsapp.ERRO_OPTOUT_MARKETING:
                db.registrar_optout(lead["id"])
        proximo_em += intervalo
        db.conn().execute("UPDATE transmissoes SET proximo_em=? WHERE id=?", (proximo_em, t["id"]))
        db.conn().commit()
    return tentou


def tick(agora: float | None = None) -> int:
    """Uma rodada da fila. Devolve quantos envios tentou."""
    agora = time.time() if agora is None else agora
    agora_iso = db.now_iso()
    for r in db.conn().execute(
            "SELECT * FROM transmissoes WHERE status='agendada' AND "
            "(agendada_para='' OR agendada_para<=?) ORDER BY id", (agora_iso,)).fetchall():
        _materializa(db.get_transmissao(r["id"]))
    tentou = 0
    for r in db.conn().execute(
            "SELECT id FROM transmissoes WHERE status='enviando' ORDER BY id").fetchall():
        tentou += _toca(db.get_transmissao(r["id"]), agora)
    return tentou


def relatorio(transmissao_id) -> dict:
    t = db.get_transmissao(transmissao_id) or {}
    c = db.conn()
    linha = dict(c.execute(
        """SELECT COUNT(*) total,
                  SUM(status='pendente') pendente,
                  SUM(enviado_em<>'') enviado,
                  SUM(entregue_em<>'') entregue,
                  SUM(lido_em<>'') lido,
                  SUM(respondido_em<>'') respondido,
                  SUM(status='falhou') falhou,
                  SUM(status='pulado') pulado,
                  SUM(status IN ('revisar','enviando')) revisar
           FROM wa_envios WHERE transmissao_id=?""", (transmissao_id,)).fetchone())
    saida = {k: int(v or 0) for k, v in linha.items()}
    saida["erros"] = {int(r["erro_codigo"]): r["n"] for r in c.execute(
        """SELECT erro_codigo, COUNT(*) n FROM wa_envios WHERE transmissao_id=?
           AND erro_codigo IS NOT NULL GROUP BY erro_codigo""", (transmissao_id,))}
    por_cat, custo = {}, 0.0
    for r in c.execute(
            """SELECT COALESCE(NULLIF(categoria,''), ?) cat, COUNT(*) n FROM wa_envios
               WHERE transmissao_id=? AND cobravel=1 GROUP BY cat""",
            (t.get("categoria") or "marketing", transmissao_id)):
        por_cat[r["cat"]] = r["n"]
        custo += r["n"] * preco(r["cat"])
    saida["por_categoria"] = por_cat
    # custo_usd é o que a Meta já marcou como cobrável; o previsto usa a mesma conta do
    # formulário (público × preço da categoria). Antes de disparar a fila ainda não
    # existe, então o público é contado agora; depois, quem falhou ou foi pulado sai.
    saida["custo_usd"] = round(custo, 4)
    if saida["total"]:
        alvo = saida["total"] - saida["falhou"] - saida["pulado"]
    elif t:
        alvo = db.contar_publico(t["account_id"], t["publico"])
    else:
        alvo = 0
    saida["previsto"] = alvo
    saida["custo_previsto_usd"] = round(alvo * preco(t.get("categoria") or "marketing"), 4)
    saida["erros_explicados"] = [{**explicar_erro(c), "n": n}
                                 for c, n in sorted(saida["erros"].items(), key=lambda x: -x[1])]
    return saida
