"""Segredos que entram pelo painel. Cifrados com CEQ_ENCRYPTION_KEY (Fernet).

Três estados da chave, e o painel mostra cada um:
- ok: cifra. Valor que estava em claro (raw:) é recifrado na primeira leitura.
- ausente (instância antiga): guarda em claro e o painel avisa.
- invalida (chave mal formada no .env): também guarda em claro, mas registra aviso
  no log e o painel diz "chave inválida". Antes isso caía calado no "sem chave", e
  o dono achava que estava cifrando.
"""
import logging
import os

from . import db

log = logging.getLogger("ceq.segredos")


def _fernet():
    """Fernet pronto, ou None sem chave. Levanta se a chave for inválida."""
    k = os.environ.get("CEQ_ENCRYPTION_KEY", "")
    if not k:
        return None
    from cryptography.fernet import Fernet
    return Fernet(k.encode())


def estado_chave() -> str:
    """'ok', 'ausente' ou 'invalida'."""
    if not os.environ.get("CEQ_ENCRYPTION_KEY", ""):
        return "ausente"
    try:
        _fernet()
    except Exception:
        return "invalida"
    return "ok"


def cifrado_disponivel() -> bool:
    return estado_chave() == "ok"


def _gravar(chave: str, valor: str) -> None:
    estado = estado_chave()
    if estado == "ok":
        db.set_ajuste(f"seg:{chave}", "enc:" + _fernet().encrypt(valor.encode()).decode())
        return
    if estado == "invalida":
        log.warning("CEQ_ENCRYPTION_KEY inválida: %s guardado sem cifra", chave)
    db.set_ajuste(f"seg:{chave}", "raw:" + valor)


def guardar(chave: str, valor: str) -> None:
    _gravar(chave, valor)


def ler(chave: str) -> str:
    bruto = db.get_ajuste(f"seg:{chave}", "")
    if not bruto:
        return ""
    if bruto.startswith("raw:"):
        valor = bruto[4:]
        # chave chegou depois do valor (instância que ganhou CEQ_ENCRYPTION_KEY):
        # aproveita a leitura pra tirar o valor do claro
        if valor and cifrado_disponivel():
            _gravar(chave, valor)
        return valor
    if not cifrado_disponivel():
        return ""
    try:
        return _fernet().decrypt(bruto[4:].encode()).decode()
    except Exception:
        return ""
