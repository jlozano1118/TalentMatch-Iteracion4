"""Autenticación: bcrypt + JWT en cookie HttpOnly, bloqueo por intentos fallidos."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.config import ALLOWED_DOMAIN, JWT_SECRET, LOCKOUT_MINUTES, MAX_LOGIN_ATTEMPTS, SESSION_HOURS
from app.database.models import User
from app.persistence.repositories.candidates import AuditRepository
from app.persistence.repositories.users import UserRepository

EMAIL_RX = re.compile(r"^[a-z0-9._-]{3,40}@" + re.escape(ALLOWED_DOMAIN) + r"$")
# Hash ficticio para igualar tiempos de respuesta cuando el usuario no existe (evita enumeración)
_DUMMY_HASH = bcrypt.hashpw(b"talentmatch-dummy", bcrypt.gensalt(12))


class AuthError(Exception):
    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.status = status


def authenticate(db: Session, email: str, password: str) -> User:
    email = (email or "").strip().lower()
    audit = AuditRepository(db)
    if not EMAIL_RX.match(email):
        raise AuthError(f"Use su correo corporativo @{ALLOWED_DOMAIN}.", 400)
    repo = UserRepository(db)
    user = repo.by_email(email)
    now = datetime.utcnow()
    if user is None:
        bcrypt.checkpw((password or "x").encode("utf-8"), _DUMMY_HASH)
        audit.log(email, "login_fallido", "usuario", "", "Usuario no autorizado")
        raise AuthError("Credenciales inválidas.")
    if user.locked_until and user.locked_until > now:
        mins = int((user.locked_until - now).total_seconds() // 60) + 1
        raise AuthError(f"Cuenta bloqueada temporalmente por seguridad. Intente en {mins} min.", 423)
    if not bcrypt.checkpw((password or "").encode("utf-8"), user.password_hash.encode("utf-8")):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_LOGIN_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_attempts = 0
            audit.log(email, "cuenta_bloqueada", "usuario", "", f"{MAX_LOGIN_ATTEMPTS} intentos fallidos")
        repo.save(user)
        audit.log(email, "login_fallido", "usuario", "", "Contraseña incorrecta")
        raise AuthError("Credenciales inválidas.")
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login = now
    repo.save(user)
    audit.log(email, "login", "usuario")
    return user


def create_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
    return jwt.encode({"sub": str(user.id), "email": user.email, "exp": exp}, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
