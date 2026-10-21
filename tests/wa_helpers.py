"""Montadores de payload do webhook do WhatsApp, no formato da Cloud API."""
import uuid


def _envelope(phone_id, value, field="messages"):
    value = {"messaging_product": "whatsapp",
             "metadata": {"display_phone_number": "5511400000000", "phone_number_id": phone_id},
             **value}
    return {"object": "whatsapp_business_account",
            "entry": [{"id": "waba1", "changes": [{"field": field, "value": value}]}]}


def _msg(phone_id, wa_id, nome="", mid=None, **corpo):
    m = {"from": wa_id, "id": mid or f"wamid.in.{uuid.uuid4().hex}", "timestamp": "1760000000", **corpo}
    return _envelope(phone_id, {"contacts": [{"profile": {"name": nome}, "wa_id": wa_id}],
                                "messages": [m]})


def _status(phone_id, wamid, status, **extra):
    return _envelope(phone_id, {"statuses": [{"id": wamid, "status": status,
                                              "timestamp": "1760000000",
                                              "recipient_id": "5511900000000", **extra}]})
