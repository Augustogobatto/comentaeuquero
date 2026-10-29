"""Normalização de texto usada pelo motor (palavra-chave) e pelo passo de IA.

Fica num módulo sem dependência nenhuma do app: flowengine importa runtime, então o
helper comum não pode morar em nenhum dos dois.
"""
import unicodedata


def sem_acento(s: str) -> str:
    """Minúsculo e sem acento (NFD, tira as marcas combinantes). "Ação" -> "acao"."""
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()
