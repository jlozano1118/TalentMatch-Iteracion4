"""Punto de entrada para plataformas que ejecutan `uvicorn main:app` (Render, Railway, etc.).

La aplicación real vive en app/main.py (arquitectura por capas); aquí sólo se re-exporta.
"""
from app.main import app  # noqa: F401
