"""Aviso pro dono quando a instância se segura sozinha (vigia).

Opcional de propósito: sem token e chat configurados, não faz nada e o produto não
ganha dependência nova. Com eles, o dono fica sabendo na hora que a instância
entrou em cooldown de rate limit, em vez de descobrir dias depois olhando log.
Sistema que se limita em silêncio é sistema que falha em silêncio com atraso.

A credencial mora em `ajustes` (editável na aba Configurações, sem restart); o
.env é só a semente da primeira subida. O valor "off" no ajuste significa que o
dono desativou pelo painel, e aí nem o .env religa.
"""
import os
import threading

import requests

from . import db


def credenciais() -> tuple:
    tok = db.get_ajuste("alerta_telegram_token")
    chat = db.get_ajuste("alerta_telegram_chat")
    if tok == "off":
        return "", ""
    if not tok:
        tok = os.environ.get("ALERTA_TELEGRAM_TOKEN", "")
        chat = chat or os.environ.get("ALERTA_TELEGRAM_CHAT", "")
    return tok, chat


def avisar(texto: str, sincrono: bool = False) -> bool:
    """Dispara e esquece: alerta nunca pode travar nem derrubar um envio.

    `sincrono=True` espera a resposta do Telegram e diz se chegou. É o modo do
    botão "enviar teste" do painel, onde o ponto é justamente ver se funciona.
    """
    token, chat = credenciais()
    if not (token and chat):
        return False

    def _manda() -> bool:
        try:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                              json={"chat_id": chat, "text": texto}, timeout=10)
            return r.status_code == 200
        except requests.RequestException:
            return False

    if sincrono:
        return _manda()
    threading.Thread(target=_manda, daemon=True).start()
    return True
