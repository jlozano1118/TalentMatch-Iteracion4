"""Cifrado en reposo de datos personales (Fernet: AES-128-CBC + HMAC-SHA256)."""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import ENCRYPTION_KEY


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(ENCRYPTION_KEY.encode())


def encrypt(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str | None) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return "[ilegible: llave de cifrado distinta]"


def mask_email(email: str) -> str:
    if "@" not in email:
        return ""
    user, dom = email.split("@", 1)
    return (user[:2] + "•" * max(1, len(user) - 2)) + "@" + dom


def mask_phone(phone: str) -> str:
    digits = [c for c in phone if c.isdigit()]
    return ("•" * max(0, len(digits) - 3)) + "".join(digits[-3:]) if digits else ""
