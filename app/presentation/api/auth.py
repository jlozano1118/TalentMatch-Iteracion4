from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.business.auth_service import AuthError, authenticate, create_token
from app.config import COOKIE_SECURE, SESSION_HOURS
from app.database.connection import get_db
from app.database.models import User
from app.persistence.repositories.candidates import AuditRepository
from app.presentation.dependencies import COOKIE_NAME, current_user

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


class LoginIn(BaseModel):
    email: str = Field(max_length=120)
    password: str = Field(max_length=128)


def _user_view(u: User) -> dict:
    return {"email": u.email, "name": u.display_name, "role": u.role,
            "initials": "".join(w[0] for w in u.display_name.split()[:2]).upper()}


@router.post("/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    try:
        user = authenticate(db, body.email, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    response.set_cookie(COOKIE_NAME, create_token(user), httponly=True, samesite="strict", secure=COOKIE_SECURE,
                        max_age=SESSION_HOURS * 3600, path="/")
    return {"user": _user_view(user)}


@router.post("/logout")
def logout(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    AuditRepository(db).log(user.email, "logout", "usuario")
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"user": _user_view(user)}
