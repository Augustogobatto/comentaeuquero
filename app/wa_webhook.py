"""Entrada do WhatsApp: o objeto `whatsapp_business_account` que chega no /webhook.

Três famílias de evento, todas dentro de entry[].changes[]:
  messages          mensagem da pessoa (texto, clique em botão/lista, botão de template)
                    e status do que a gente mandou (enviado, entregue, lido, falhou)
  user_preferences  a pessoa parou/voltou a aceitar marketing pelo próprio WhatsApp
  phone_number_quality_update  qualidade e limite do número mudaram
  business_capability_update   o limite do portfólio subiu (pedido de aumento aprovado)

Chamado já dentro do PROCESS_LOCK (flowengine.process_payload). Número que não é de
nenhuma conta desta instância só vira um evento `webhook_sem_conta`: nenhum lead é
criado e nada sai pra Meta.
"""
from . import db, whatsapp

TEXTO_OPTOUT = ("Pronto, você não vai mais receber nossas mensagens por aqui. "
                "Se mudar de ideia, mande VOLTAR.")
TEXTO_VOLTOU = "Combinado, você voltou a receber nossas mensagens."


def _quem(lead) -> str:
    return lead.get("username") or lead.get("wa_id") or lead.get("igsid") or ""


def process(payload: dict) -> None:
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            campo = change.get("field")
            valor = change.get("value") or {}
            if campo == "messages":
                _mensagens(valor)
            elif campo == "user_preferences":
                _preferencias(valor)
            elif campo == "phone_number_quality_update":
                _qualidade(entry, valor)
            elif campo == "business_capability_update":
                _capacidade(entry, valor)


def _conta_de(valor):
    pn = str((valor.get("metadata") or {}).get("phone_number_id") or "")
    conta = db.get_account_by_wa_phone(pn)
    if not conta:
        db.log_event("webhook_sem_conta", payload={"phone_number_id": pn})
    return conta


def _mensagens(valor):
    conta = _conta_de(valor)
    if not conta:
        return
    nomes = {str(c.get("wa_id")): (c.get("profile") or {}).get("name", "")
             for c in valor.get("contacts") or []}
    for m in valor.get("messages") or []:
        _uma_mensagem(conta, m, nomes)
    for st in valor.get("statuses") or []:
        _um_status(conta, st)


def _uma_mensagem(conta, m, nomes):
    remetente = str(m.get("from") or "")
    if not remetente or not m.get("id"):
        return
    if not db.claim(m["id"]):
        return   # reentrega da Meta
    lead = db.lead_por_wa(conta["id"], remetente, nomes.get(remetente, ""),
                          whatsapp.variantes(remetente))
    db.abrir_janela(lead["id"], "wa")
    # iniciar conversa no WhatsApp é opt-in (decisão 5 da spec)
    db.registrar_optin(lead["id"], "conversa")
    marcar = getattr(db, "marcar_respondido_wa", None)
    if marcar:
        marcar(lead["id"])
    lead = db.get_lead(lead["id"])

    tipo = m.get("type")
    if tipo == "text":
        texto = (m.get("text") or {}).get("body", "")
        if whatsapp.e_optout(texto):
            db.registrar_optout(lead["id"])
            # quem pediu pra sair não recebe nem o resto do fluxo que estava rodando
            sessao = _sessao_wa(lead)
            if sessao:
                db.cancel_jobs_of_session(sessao["id"])
                db.update_session(sessao["id"], status="concluida")
            whatsapp.send_text(conta, lead["wa_id"], TEXTO_OPTOUT)
            db.log_event("wa_optout", conta["id"], source="wa_texto", ok=True, who=_quem(lead))
            return
        if whatsapp.e_optin_de_volta(texto) and lead.get("wa_optout_em"):
            db.limpar_optout(lead["id"])
            whatsapp.send_text(conta, lead["wa_id"], TEXTO_VOLTOU)
            db.log_event("wa_optin_volta", conta["id"], source="wa_texto", ok=True,
                         who=_quem(lead))
            return
        _texto(conta, lead, texto)
        return
    if tipo == "interactive":
        i = m.get("interactive") or {}
        chave = ((i.get("button_reply") or {}).get("id")
                 or (i.get("list_reply") or {}).get("id") or "")
        _resposta_interativa(conta, lead, chave)
        return
    if tipo == "button":
        b = m.get("button") or {}
        _botao_template(conta, lead, b.get("payload", ""), b.get("text", ""))
        return
    db.log_event("wa_mensagem", conta["id"], source=str(tipo or ""), who=_quem(lead),
                 payload={"tipo": tipo})


def _um_status(conta, st):
    pricing = st.get("pricing") or {}
    erros = st.get("errors") or []
    codigo = (erros[0] or {}).get("code") if erros else None
    linha = db.aplicar_status_wa(st.get("id", ""), st.get("status", ""),
                                 pricing.get("category", ""), bool(pricing.get("billable")),
                                 codigo)
    if not linha:
        return
    lead = db.get_lead(linha["lead_id"]) if linha.get("lead_id") else None
    if (linha["mudou"] and linha["status"] == "lido" and linha.get("origem") == "fluxo"
            and lead):
        # mesma etapa "leram" do funil do Instagram
        db.log_event("fluxo_lido", conta["id"], linha.get("flow_name", ""), "leitura_wa",
                     True, _quem(lead), {})
    if codigo is not None:
        try:
            codigo = int(codigo)
        except (TypeError, ValueError):
            codigo = 0
        if codigo == whatsapp.ERRO_OPTOUT_MARKETING and lead:
            db.registrar_optout(lead["id"])
        elif codigo == whatsapp.ERRO_FORA_JANELA:
            db.log_event("fora_da_janela", conta["id"], linha.get("flow_name", ""), "wa", 0,
                         _quem(lead) if lead else "", {"wamid": st.get("id", "")})


def _preferencias(valor):
    conta = _conta_de(valor)
    if not conta:
        return
    for p in valor.get("user_preferences") or []:
        if p.get("category") != "marketing_messages":
            continue
        wa_id = str(p.get("wa_id") or "")
        if not wa_id:
            continue
        lead = db.lead_por_wa(conta["id"], wa_id, "", whatsapp.variantes(wa_id))
        if p.get("value") == "stop":
            db.registrar_optout(lead["id"])
        elif p.get("value") == "resume":
            db.limpar_optout(lead["id"])


def _conta_da_waba(entry):
    """Eventos da WABA vêm sem phone_number_id: a conta é achada pela WABA (entry.id)."""
    waba = str(entry.get("id") or "")
    r = db.conn().execute("SELECT * FROM accounts WHERE wa_waba_id=? AND wa_waba_id<>'' LIMIT 1",
                          (waba,)).fetchone()
    if not r:
        db.log_event("webhook_sem_conta", payload={"waba_id": waba})
        return None
    return dict(r)


def _limite_do_evento(valor, atual):
    """Limite novo do evento, ou o que a conta já tinha. Ordem: o campo do portfólio
    (v24+), o por número (v23 e anteriores), e o current_limit que a Meta tirou em
    fev/2026."""
    for campo in ("max_daily_conversations_per_business", "max_daily_conversation_per_phone",
                  "current_limit"):
        if valor.get(campo) not in (None, ""):
            return whatsapp.limite_de_tier(valor[campo])
    return atual


def _qualidade(entry, valor):
    """A Meta avisa quando a qualidade ou o limite do número mudam."""
    conta = _conta_da_waba(entry)
    if not conta:
        return
    limite = _limite_do_evento(valor, conta.get("wa_limite"))
    evento = str(valor.get("event") or "")
    qualidade = {"FLAGGED": "RED", "UNFLAGGED": "GREEN"}.get(evento, conta.get("wa_qualidade") or "")
    db.update_wa_estado(conta["id"], conta.get("wa_numero") or "", conta.get("wa_nome") or "",
                        qualidade, limite)
    db.log_event("wa_qualidade", conta["id"], payload={"evento": evento, "limite": limite})


def _capacidade(entry, valor):
    """Pedido de aumento de limite aprovado: só o limite muda."""
    conta = _conta_da_waba(entry)
    if not conta:
        return
    limite = _limite_do_evento(valor, conta.get("wa_limite"))
    db.update_wa_estado(conta["id"], conta.get("wa_numero") or "", conta.get("wa_nome") or "",
                        conta.get("wa_qualidade") or "", limite)
    db.log_event("wa_qualidade", conta["id"], payload={"evento": "capacidade", "limite": limite})


# ---------- gatilhos e retomada de sessão ----------
#
# Só sessão do canal WA é retomada por mensagem do WA: quem está no meio de um fluxo
# no direct e manda algo no WhatsApp não tem a conversa do Instagram respondida aqui.

def _sessao_wa(lead):
    from . import runtime
    s = db.active_session_for_lead(lead["id"])
    return s if s and runtime.canal_de(s) == "wa" else None


def _texto(conta, lead, texto):
    from . import flowengine, runtime
    sessao = _sessao_wa(lead)
    if sessao and sessao.get("waiting_for") == "text":
        motivo = runtime.resume_text(conta, lead, texto)
        db.log_event("fluxo_resposta", conta["id"], db.flow_name_do_lead(lead["id"]),
                     "wa_texto", True, _quem(lead), {"motivo": motivo})
        return
    if sessao and sessao.get("waiting_for") == "template" and hasattr(runtime, "resume_template"):
        motivo = runtime.resume_template(conta, lead, texto, payload=None)
        db.log_event("fluxo_resposta", conta["id"], db.flow_name_do_lead(lead["id"]),
                     "wa_texto", True, _quem(lead), {"motivo": motivo})
        return
    gatilho = flowengine.match_trigger(conta["id"], "wa_message", texto)
    if not gatilho:
        db.log_event("sem_keyword", conta["id"], "", "wa_message", None, _quem(lead),
                     {"text": (texto or "")[:200]})
        return
    flowengine._dispara(conta, gatilho, lead, "wa_message", texto, canal="wa")


def _resposta_interativa(conta, lead, chave):
    from . import runtime
    sessao = _sessao_wa(lead)
    if not sessao or sessao.get("waiting_for") != "postback":
        db.log_event("wa_clique_sem_sessao", conta["id"], source="wa_botao", who=_quem(lead),
                     payload={"chave": chave})
        return
    motivo = runtime.resume_postback(conta, lead, chave)
    db.log_event("fluxo_postback", conta["id"], db.flow_name_do_lead(lead["id"]), "wa_botao",
                 motivo not in ("sem_sessao_esperando", "sem_fluxo"), _quem(lead),
                 {"motivo": motivo, "payload": chave})


def _botao_template(conta, lead, payload, texto):
    from . import flowengine, runtime
    sessao = _sessao_wa(lead)
    if sessao and sessao.get("waiting_for") == "template" and hasattr(runtime, "resume_template"):
        motivo = runtime.resume_template(conta, lead, texto, payload=payload or texto)
        db.log_event("fluxo_postback", conta["id"], db.flow_name_do_lead(lead["id"]),
                     "wa_botao", motivo not in ("sem_sessao_esperando", "sem_fluxo"),
                     _quem(lead), {"motivo": motivo, "payload": payload or texto})
        return
    gatilho = flowengine.match_trigger(conta["id"], "wa_template_reply", texto or payload)
    if not gatilho:
        db.log_event("wa_mensagem", conta["id"], source="wa_botao_template", who=_quem(lead),
                     payload={"payload": payload})
        return
    flowengine._dispara(conta, gatilho, lead, "wa_template_reply", texto or payload, canal="wa")
