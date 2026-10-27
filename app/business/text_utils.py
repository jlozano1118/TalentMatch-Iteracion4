"""Utilidades de normalización de texto (ES/EN)."""
from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    if text.isascii():
        return text
    t = text.replace("\u2019", "'").replace("\u2013", "-").replace("\u2014", "-").replace("\ufffd", "'")
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")


def norm(text: str) -> str:
    """Minúsculas, sin tildes, espacios colapsados y puntuación de borde removida."""
    if not text:
        return ""
    t = strip_accents(str(text)).lower()
    t = t.replace("’", "'").replace("–", "-").replace("—", "-")
    t = re.sub(r"[\*#•·▪►●]+", " ", t)
    t = _WS.sub(" ", t).strip(" .,:;-_/|()[]{}\"'")
    return t


def clean_display(text: str) -> str:
    t = _WS.sub(" ", str(text or "")).strip(" .,:;-_*#")
    return t


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9\+\#\.]+", norm(text))


def fix_mojibake(text: str) -> str:
    """Repara caracteres de reemplazo comunes de los CSV (p. ej. 'you�ll')."""
    if not isinstance(text, str):
        return ""
    return text.replace("�", "'")
