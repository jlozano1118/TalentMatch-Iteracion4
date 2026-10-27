"""Centro de privacidad: consentimiento, derechos del titular (habeas data) y retención.

Marco: Ley 1581 de 2012 y Decreto 1377 de 2013 (Colombia), RGPD (UE 2016/679),
AI Act (UE 2024/1689) — los sistemas de IA para selección y gestión de personal son de
ALTO RIESGO (Anexo III, num. 4): exige supervisión humana, transparencia y registros.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.config import PRIVACY_POLICY_VERSION, RETENTION_DAYS
from app.database.models import Candidate, Consent, User
from app.persistence.crypto import decrypt
from app.persistence.repositories.candidates import AuditRepository, CandidateRepository

PURPOSES = {
    "matching": "Evaluar la compatibilidad del colaborador con cargos de proyectos internos (movilidad interna).",
    "capacitacion": "Generar un plan de capacitación personalizado para cerrar brechas de habilidades.",
}
EXTERNAL_AI_PURPOSE = ("Procesar el texto de la hoja de vida, previamente anonimizado, con un proveedor externo de IA "
                       "(API de Claude, Anthropic) para enriquecer la extracción de habilidades.")

POLICY = {
    "version": PRIVACY_POLICY_VERSION,
    "responsable": "Área de Talento Humano — TalentMatch (uso interno)",
    "finalidades": PURPOSES,
    "finalidad_opcional": EXTERNAL_AI_PURPOSE,
    "datos_tratados": [
        "Nombre y datos de contacto (cifrados en reposo; no participan en el matching).",
        "Habilidades técnicas, power skills, experiencia laboral, formación, idiomas y certificaciones.",
    ],
    "datos_excluidos": [
        "Documento de identidad, fecha de nacimiento, edad, sexo/género, estado civil, religión, origen, salud, "
        "afiliación política o sindical, fotografía, dirección de residencia y referencias de terceros.",
        "Estos datos se detectan y descartan automáticamente: no se usan ni se almacenan.",
    ],
    "derechos": [
        "Conocer, actualizar y rectificar sus datos (Ley 1581, art. 8a).",
        "Solicitar prueba de la autorización otorgada (art. 8b).",
        "Ser informado del uso dado a sus datos (art. 8c).",
        "Revocar la autorización y/o solicitar la supresión de sus datos (art. 8e) — derecho al olvido (RGPD art. 17).",
        "Acceder gratuitamente a sus datos (art. 8f) y a la portabilidad (RGPD art. 20).",
        "No ser objeto de decisiones basadas únicamente en tratamiento automatizado (RGPD art. 22): "
        "toda asignación la decide y justifica una persona de Talento Humano.",
    ],
    "retencion": f"Los datos se conservan máximo {RETENTION_DAYS} días y luego se eliminan automáticamente.",
    "seguridad": "Cifrado Fernet (AES-128 + HMAC) para datos de contacto, contraseñas con bcrypt, sesión JWT en cookie "
                 "HttpOnly/SameSite, bitácora de auditoría sin datos personales.",
    "texto_autorizacion": (
        "Declaro que el titular de la hoja de vida, de manera previa, expresa e informada, autorizó a la empresa para "
        "tratar sus datos personales con las finalidades descritas, conforme a la Ley 1581 de 2012 y el Decreto 1377 "
        "de 2013, y que fue informado de sus derechos y de que los resultados son recomendaciones que no sustituyen "
        "la decisión humana."
    ),
}


def register_consent(db: Session, user: User, purposes: list[str], external_ai: bool, attested: bool) -> Consent:
    if not attested:
        raise ValueError("Se requiere la autorización expresa del titular (Ley 1581 de 2012, art. 9).")
    if "matching" not in purposes:
        raise ValueError("La finalidad de matching es necesaria para analizar la hoja de vida.")
    valid = [p for p in purposes if p in PURPOSES]
    consent = Consent(policy_version=PRIVACY_POLICY_VERSION, purposes=valid, external_ai=bool(external_ai),
                      recorded_by=user.id)
    return CandidateRepository(db).add_consent(consent)


def export_candidate(db: Session, cand: Candidate, user: User) -> dict:
    """Reporte de acceso del titular (derecho a conocer / portabilidad)."""
    repo = CandidateRepository(db)
    AuditRepository(db).log(user.email, "exportar_datos_titular", "candidato", cand.code)
    return {
        "reporte": "Reporte de datos personales del titular — TalentMatch",
        "generado": datetime.utcnow().isoformat() + "Z",
        "codigo": cand.code,
        "identificacion": {"nombre": decrypt(cand.name_enc), "correo": decrypt(cand.email_enc),
                           "telefono": decrypt(cand.phone_enc), "ubicacion": decrypt(cand.location_enc)},
        "autorizacion": {"version_politica": cand.consent.policy_version, "finalidades": cand.consent.purposes,
                         "ia_externa": cand.consent.external_ai, "fecha": cand.consent.granted_at.isoformat()},
        "datos_descartados_por_sensibles": cand.sensitive_discarded,
        "perfil": {"titular_profesional": cand.headline, "anos_experiencia": cand.years_experience,
                   "nivel_educativo": cand.education_label, "habilidades_tecnicas": [s["name"] for s in cand.tech_skills],
                   "power_skills": [s["name"] for s in cand.soft_skills], "experiencia": cand.experience,
                   "educacion": cand.education, "idiomas": cand.languages, "certificaciones": cand.certifications},
        "compatibilidades": [{"proyecto": m.role.project.name, "cargo": m.role.title, "porcentaje": m.score}
                             for m in repo.matches(cand.id)],
        "planes_capacitacion": [{"cargo_id": p.role_id, "horas": p.total_hours, "semanas": p.weeks} for p in repo.plans(cand.id)],
        "decisiones_humanas": [{"cargo_id": d.role_id, "decision": d.decision, "justificacion": d.justification,
                                "fecha": d.created_at.isoformat()} for d in repo.decisions(cand.id)],
        "conservacion_hasta": cand.retention_until.date().isoformat(),
    }


def delete_candidate(db: Session, cand: Candidate, user: User, reason: str) -> None:
    code = cand.code
    CandidateRepository(db).delete(cand)
    AuditRepository(db).log(user.email, "supresion_datos", "candidato", code, reason or "Solicitud del titular")


def purge_expired(db: Session) -> int:
    repo = CandidateRepository(db)
    expired = repo.expired(datetime.utcnow())
    for c in expired:
        code = c.code
        repo.delete(c)
        AuditRepository(db).log("sistema", "supresion_por_retencion", "candidato", code, f"Plazo de {RETENTION_DAYS} días cumplido")
    return len(expired)
