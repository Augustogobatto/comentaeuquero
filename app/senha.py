"""Senha do painel.

Duas origens, nesta ordem: ADMIN_PASSWORD no .env (instâncias antigas, continua
valendo e tem precedência) e o hash guardado em `ajustes` pelo primeiro acesso
(/instalar). Mora num módulo próprio porque main.py e api.py precisam dela, e
api.py é importado por main.py.
"""
import base64
import hashlib
import hmac
import os
import secrets

from . import db

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
CHAVE_HASH = "admin_senha_hash"


def _hash_senha(senha: str, salt: bytes | None = None, iteracoes: int = 200_000) -> str:
    salt = salt or secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, iteracoes)
    return f"pbkdf2_sha256${iteracoes}${base64.b64encode(salt).decode()}${base64.b64encode(h).decode()}"


def senha_definida() -> bool:
    return bool(ADMIN_PASSWORD) or bool(db.get_ajuste(CHAVE_HASH, ""))


def definir_senha(senha: str) -> None:
    db.set_ajuste(CHAVE_HASH, _hash_senha(senha))


def conferir_senha(senha: str) -> bool:
    """Env tem precedência (instâncias antigas). Sem env, confere o hash em ajustes."""
    if ADMIN_PASSWORD:
        return hmac.compare_digest((senha or "").encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))
    guardado = db.get_ajuste(CHAVE_HASH, "")
    if not guardado:
        return False
    try:
        _, it, salt_b64, h_b64 = guardado.split("$")
        h = hashlib.pbkdf2_hmac("sha256", (senha or "").encode("utf-8"),
                                base64.b64decode(salt_b64), int(it))
        return hmac.compare_digest(h, base64.b64decode(h_b64))
    except Exception:
        return False
