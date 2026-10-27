"""Enriquecimiento OPCIONAL con la API de Claude.

Sólo se ejecuta si (1) existe ANTHROPIC_API_KEY y (2) el titular autorizó expresamente
el tratamiento por un proveedor externo de IA (casilla independiente del consentimiento).
Antes del envío se eliminan datos sensibles y se seudonimizan correo, teléfono y URLs.

Control de alucinaciones: una habilidad propuesta por el modelo sólo se acepta si su
evidencia literal aparece en el texto del CV. Lo que no tenga evidencia se descarta.
"""
from __future__ import annotations

import json
import logging
import re

from app.business.extraction.sensitive import redact_for_external
from app.business.skill_catalog import canonical_soft, canonical_tech, display_tech, soft_label
from app.business.text_utils import norm
from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, EXTERNAL_AI_ENABLED

log = logging.getLogger("talentmatch.llm")

PROMPT = """Eres un analista de talento humano. Del siguiente CV (datos personales ya anonimizados) extrae
únicamente habilidades técnicas y power skills que estén EXPLÍCITAMENTE respaldadas por el texto.
Responde sólo JSON con la forma:
{"tecnicas":[{"nombre":"...","evidencia":"fragmento literal del CV"}],
 "power_skills":[{"nombre":"...","evidencia":"fragmento literal del CV"}]}
No inventes nada. Si no hay evidencia literal, no lo incluyas.

CV:
"""


def enrich_with_claude(text: str) -> dict:
    """Devuelve {'tech': [...], 'soft': [...], 'used': bool, 'note': str}."""
    if not EXTERNAL_AI_ENABLED:
        return {"tech": [], "soft": [], "used": False, "note": "IA externa no configurada"}
    try:
        import httpx
    except ImportError:  # pragma: no cover
        return {"tech": [], "soft": [], "used": False, "note": "httpx no instalado"}

    safe_text = redact_for_external(text)[:12000]
    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": ANTHROPIC_MODEL, "max_tokens": 1500,
                  "messages": [{"role": "user", "content": PROMPT + safe_text}]},
            timeout=60,
        )
        resp.raise_for_status()
        content = "".join(b.get("text", "") for b in resp.json().get("content", []))
        m = re.search(r"\{.*\}", content, re.S)
        data = json.loads(m.group(0)) if m else {}
    except Exception as exc:  # la extracción local sigue funcionando
        log.warning("Claude API no disponible: %s", exc)
        return {"tech": [], "soft": [], "used": False, "note": "La IA externa no respondió; se usó sólo la extracción local"}

    folded_text = norm(text)
    tech, soft, rejected = [], [], 0
    for item in data.get("tecnicas", []):
        ev = str(item.get("evidencia", ""))
        if ev and norm(ev)[:60] in folded_text:
            key = canonical_tech(item.get("nombre", ""))
            tech.append({"key": key, "name": display_tech(key), "confidence": 0.8, "evidence": ev[:160],
                         "source": "IA (Claude) con evidencia verificada"})
        else:
            rejected += 1
    for item in data.get("power_skills", []):
        ev = str(item.get("evidencia", ""))
        if ev and norm(ev)[:60] in folded_text:
            sk = canonical_soft(item.get("nombre", "")) or norm(item.get("nombre", ""))
            soft.append({"key": sk, "name": soft_label(sk), "confidence": 0.75, "evidence": ev[:160],
                         "source": "IA (Claude) con evidencia verificada"})
        else:
            rejected += 1
    return {"tech": tech, "soft": soft, "used": True,
            "note": f"Claude propuso {len(tech) + len(soft) + rejected} habilidades; {rejected} descartadas por falta de evidencia"}
