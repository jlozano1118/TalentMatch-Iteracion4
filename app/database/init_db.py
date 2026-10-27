"""Creación del esquema y datos semilla mínimos (usuarios autorizados y proyectos)."""
from __future__ import annotations

from app.database import models  # noqa: F401  (registra las tablas)
from app.database.connection import Base, engine

# Únicos usuarios autorizados (dominio @talentmatch.co). Sólo se guardan hashes bcrypt
# (coste 12); las contraseñas en claro NO están en el repositorio.
AUTHORIZED_USERS = [
    {"email": "jslozano95@talentmatch.co", "display_name": "Juan Sebastián Lozano Calderón",
     "password_hash": "$2b$12$LVhyPyYROsohuxogJSEWZex0Wh6swAbYKa9LB9PYER8wnD6UP2Fkm"},
    {"email": "adrojas53@talentmatch.co", "display_name": "Andrés Favid Rojas Villamil",
     "password_hash": "$2b$12$.QU/JbSJpfhov3QLpYTY9u8I34d0w1rsz6qW3ysMNtabbyI6jIHSO"},
    {"email": "jslopez59@talentmatch.co", "display_name": "Juan Sebastián López Urrego",
     "password_hash": "$2b$12$zeT1nH47rH1k.Hw7Lutjv.e/nhDuPwR1BtECRC7jRduYQk5d3jI1y"},
    {"email": "joromero10@talentmatch.co", "display_name": "Jeison Oswaldo Romero Cajamarca",
     "password_hash": "$2b$12$PXFJVUwBfyVX6WhU5Zxh6uaT8skJMl96hzuYBGDt3t2HAkFE.Zu8q"},
]


def create_schema() -> None:
    Base.metadata.create_all(bind=engine)
