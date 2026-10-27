"""TalentMatch · Iteración 4 — punto de entrada FastAPI.

Arquitectura por capas:
  presentation/  → API REST + interfaz web (HTML/CSS/JS)
  business/      → extracción de CV, matching, plan de capacitación, privacidad, ética
  persistence/   → repositorios, datasets y cifrado
  database/      → motor SQLite, modelo ORM y datos semilla
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.business.bootstrap import init_app
from app.config import APP_NAME, APP_VERSION
from app.presentation.api import auth, candidates, catalog, ethics

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
WEB = Path(__file__).parent / "presentation" / "web"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_app()
    yield


app = FastAPI(title=f"{APP_NAME} API", version=APP_VERSION, lifespan=lifespan,
              docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if not request.url.path.startswith("/api/docs"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; media-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):  # pragma: no cover
    logging.getLogger("talentmatch").exception("Error no controlado: %s", exc)
    return JSONResponse({"detail": "Ocurrió un error interno. Intente nuevamente."}, status_code=500)


app.include_router(auth.router)
app.include_router(candidates.router)
app.include_router(catalog.router)
app.include_router(ethics.router)
app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB / "templates" / "index.html")


@app.get("/api/health", include_in_schema=False)
def health():
    return {"status": "ok", "app": APP_NAME, "version": APP_VERSION}
