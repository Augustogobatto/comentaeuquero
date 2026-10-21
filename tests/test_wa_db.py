"""Modelo de dados do WhatsApp: lead só-WA, variantes do 9, fusão IG+WA, janela por canal."""
import uuid

from app import db


def _conta():
    return db.upsert_account(uuid.uuid4().hex, "", "conta_teste", "tok", "2099-01-01T00:00:00Z")


def test_init_idempotente_e_colunas():
    db.init(); db.init()
    cols = {r[1] for r in db.conn().execute("PRAGMA table_info(leads)")}
    assert {"wa_id", "ig_janela_ate", "wa_janela_ate", "wa_optin_em", "wa_optout_em"} <= cols
    assert "canal" in {r[1] for r in db.conn().execute("PRAGMA table_info(flow_sessions)")}


def test_lead_so_wa_criado_e_reencontrado():
    c = _conta()
    a = db.lead_por_wa(c["id"], "5511987654321", "Ana")
    b = db.lead_por_wa(c["id"], "5511987654321")
    assert a["id"] == b["id"] and a["igsid"] == "wa:5511987654321" and db.e_so_wa(a)
    assert b["interactions"] == 2 and b["name"] == "Ana"


def test_lead_por_wa_acha_variante_sem_nove():
    c = _conta()
    a = db.lead_por_wa(c["id"], "5511987654321")
    b = db.lead_por_wa(c["id"], "551187654321", variantes=["551187654321", "5511987654321"])
    assert b["id"] == a["id"] and b["wa_id"] == "551187654321"


def test_vincular_funde_lead_so_wa_no_do_ig():
    c = _conta()
    wa = db.lead_por_wa(c["id"], "5511911112222")
    db.add_tag(wa["id"], "veio_wa"); db.set_field(wa["id"], "cidade", "SP"); db.set_field(wa["id"], "email", "wa@x")
    db.registrar_optin(wa["id"], "conversa")
    sid = db.open_session(c["id"], wa["id"], db.create_flow(c["id"]), canal="wa")
    ig = db.touch_lead(c["id"], "igsid-1", username="ana")
    db.set_field(ig["id"], "email", "ig@x")
    r = db.vincular_whatsapp(ig["id"], "5511911112222")
    assert r == {"resultado": "fundido", "lead_id": ig["id"]}
    assert db.get_lead(wa["id"]) is None
    lead = db.get_lead(ig["id"])
    assert lead["wa_id"] == "5511911112222" and lead["wa_optin_em"]
    assert db.has_tag(ig["id"], "veio_wa")
    assert db.lead_fields(ig["id"]) == {"email": "ig@x", "cidade": "SP", "whatsapp": "5511911112222"}
    assert db.get_session(sid)["lead_id"] == ig["id"]


def _ativas(lead_id):
    return [r["id"] for r in db.conn().execute(
        "SELECT id FROM flow_sessions WHERE lead_id=? AND status='ativa'", (lead_id,))]


def test_fusao_deixa_so_a_sessao_mais_recente_ativa():
    c = _conta()
    fluxo = db.create_flow(c["id"])
    ig = db.touch_lead(c["id"], "igsid-fus")
    s_ig = db.open_session(c["id"], ig["id"], fluxo, canal="ig")
    db.conn().execute("UPDATE flow_sessions SET updated_at='2026-01-01T00:00:00Z' WHERE id=?", (s_ig,))
    wa = db.lead_por_wa(c["id"], "5511922223333")
    s_wa = db.open_session(c["id"], wa["id"], fluxo, canal="wa")
    job = db.schedule_job(s_ig, "n1", db.in_seconds_iso(60))
    db.conn().commit()
    assert db.vincular_whatsapp(ig["id"], "5511922223333")["resultado"] == "fundido"
    assert _ativas(ig["id"]) == [s_wa]
    velha = db.get_session(s_ig)
    assert velha["status"] == "concluida" and velha["context"].get("encerrada_motivo") == "fusao_de_leads"
    assert db.conn().execute("SELECT status FROM jobs WHERE id=?", (job,)).fetchone()[0] == "cancelado"
    ev = db.conn().execute("SELECT payload FROM events WHERE kind='sessao_encerrada' AND account_id=?", (c["id"],)).fetchone()
    assert ev and "fusao_de_leads" in ev["payload"]


def test_fusao_mantem_a_sessao_em_andamento():
    """Quem está respondendo o Pedir WhatsApp no direct é a sessão viva, mesmo que a
    do WhatsApp tenha sido mexida depois."""
    c = _conta()
    fluxo = db.create_flow(c["id"])
    ig = db.touch_lead(c["id"], "igsid-fus2")
    s_ig = db.open_session(c["id"], ig["id"], fluxo, canal="ig")
    db.conn().execute("UPDATE flow_sessions SET updated_at='2026-01-01T00:00:00Z' WHERE id=?", (s_ig,))
    wa = db.lead_por_wa(c["id"], "5511922224444")
    s_wa = db.open_session(c["id"], wa["id"], fluxo, canal="wa")
    db.conn().commit()
    db.vincular_whatsapp(ig["id"], "5511922224444", sessao_atual=s_ig)
    assert _ativas(ig["id"]) == [s_ig] and db.get_session(s_wa)["status"] == "concluida"


def test_vincular_conflito_entre_dois_leads_do_ig():
    c = _conta()
    a = db.touch_lead(c["id"], "ig-a"); b = db.touch_lead(c["id"], "ig-b")
    assert db.vincular_whatsapp(a["id"], "5521900000000")["resultado"] == "vinculado"
    r = db.vincular_whatsapp(b["id"], "5521900000000")
    assert r["resultado"] == "conflito" and db.get_lead(b["id"])["wa_id"] == ""
    assert db.get_field(b["id"], "whatsapp") == "5521900000000"
    assert db.conn().execute("SELECT COUNT(*) FROM events WHERE kind='wa_conflito' AND account_id=?", (c["id"],)).fetchone()[0] == 1


def test_vincular_mesmo_numero_de_novo_e_ja_vinculado():
    c = _conta()
    a = db.touch_lead(c["id"], "ig-rep")
    assert db.vincular_whatsapp(a["id"], "5521900000001")["resultado"] == "vinculado"
    assert db.vincular_whatsapp(a["id"], "5521900000001")["resultado"] == "ja_vinculado"


def test_janela_por_canal():
    c = _conta(); l = db.touch_lead(c["id"], "ig-j")
    assert not db.janela_aberta(l, "wa")
    db.abrir_janela(l["id"], "wa")
    l = db.get_lead(l["id"])
    assert db.janela_aberta(l, "wa") and not db.janela_aberta(l, "ig")


def test_optin_nao_sobrescreve_e_optout():
    c = _conta(); l = db.lead_por_wa(c["id"], "5511933334444")
    db.registrar_optin(l["id"], "pedir_whatsapp"); db.registrar_optin(l["id"], "importacao")
    assert db.get_lead(l["id"])["wa_optin_origem"] == "pedir_whatsapp"
    db.registrar_optout(l["id"]); assert db.get_lead(l["id"])["wa_optout_em"]
    db.limpar_optout(l["id"]); assert db.get_lead(l["id"])["wa_optout_em"] == ""
