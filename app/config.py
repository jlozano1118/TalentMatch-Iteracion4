"""Configuración central de TalentMatch (iteración 4).

Todos los valores sensibles se leen de variables de entorno (.env); nunca se
dejan credenciales en texto plano dentro del código fuente.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Carga un archivo .env simple (clave=valor) sin dependencias externas."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


BASE_DIR = Path(__file__).resolve().parent.parent
_load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("TM_DATA_DIR", BASE_DIR / "data"))
STORAGE_DIR = Path(os.getenv("TM_STORAGE_DIR", BASE_DIR / "storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

JOBS_CSV = DATA_DIR / "JobsDatasetProcessed.csv"
COURSERA_CSV = DATA_DIR / "Coursera.csv"
UDEMY_XLSX = DATA_DIR / "Udemy_Courses.xlsx"

DATABASE_URL = os.getenv("TM_DATABASE_URL", f"sqlite:///{(STORAGE_DIR / 'talentmatch.db').as_posix()}")


def _persistent_secret(env_name: str, filename: str, factory) -> str:
    """Obtiene un secreto del entorno o lo genera una sola vez en storage/ (ignorado por git)."""
    value = os.getenv(env_name)
    if value:
        return value
    secret_file = STORAGE_DIR / filename
    if secret_file.exists():
        return secret_file.read_text(encoding="utf-8").strip()
    value = factory()
    secret_file.write_text(value, encoding="utf-8")
    try:
        os.chmod(secret_file, 0o600)
    except OSError:
        pass
    return value


def _fernet_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


# Firma de sesiones (JWT) y cifrado en reposo de datos personales (Fernet / AES-128-CBC + HMAC)
JWT_SECRET = _persistent_secret("TM_JWT_SECRET", ".jwt.secret", lambda: secrets.token_urlsafe(48))
ENCRYPTION_KEY = _persistent_secret("TM_ENCRYPTION_KEY", ".fernet.key", _fernet_key)

SESSION_HOURS = int(os.getenv("TM_SESSION_HOURS", "8"))
COOKIE_SECURE = os.getenv("TM_COOKIE_SECURE", "false").lower() == "true"
ALLOWED_DOMAIN = "talentmatch.co"
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# Carga de archivos
MAX_UPLOAD_MB = int(os.getenv("TM_MAX_UPLOAD_MB", "10"))
ALLOWED_EXTENSIONS = {".pdf", ".json", ".png", ".jpg", ".jpeg"}

# Minimización y retención (Ley 1581 / RGPD art. 5.1.e)
RETENTION_DAYS = int(os.getenv("TM_RETENTION_DAYS", "365"))
PRIVACY_POLICY_VERSION = "TM-PTD-2026.10-v1"

# Recomendaciones de cursos
MIN_COURSE_RATING = 4.0  # estrictamente mayor a 4.0

# IA externa opcional (Claude API). Desactivada si no hay llave o si el titular no consiente.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
EXTERNAL_AI_ENABLED = bool(ANTHROPIC_API_KEY)

APP_NAME = "TalentMatch"
APP_VERSION = "4.0.0"
ITERATION = 4
