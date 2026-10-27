"""Dependencias de la capa de presentación (sesión y usuario autenticado)."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.business.auth_service import decode_token
from app.database.connection import get_db
from app.database.models import Candidate, User
from app.persistence.repositories.candidates import CandidateRepository
from app.persistence.repositories.users import UserRepository

COOKIE_NAME = "tm_session"


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    payload = decode_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="Sesión no válida o expirada.")
    user = UserRepository(db).by_id(int(payload["sub"]))
    if not user or user.email != payload.get("email"):
        raise HTTPException(status_code=401, detail="Sesión no válida.")
    return user


def candidate_or_404(cid: int, db: Session) -> Candidate:
    cand = CandidateRepository(db).by_id(cid)
    if not cand:
        raise HTTPException(status_code=404, detail="Hoja de vida no encontrada (pudo haber sido suprimida).")
    return cand
