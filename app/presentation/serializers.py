"""Conversión de entidades a vistas para la interfaz (sin exponer datos internos innecesarios)."""
from __future__ import annotations

from app.business.matching_service import CAT_ES
from app.database.models import Candidate, Match, Project, Role, TrainingPlan
from app.persistence.crypto import decrypt, mask_email, mask_phone


def role_view(r: Role) -> dict:
    return {
        "id": r.id, "job_id": r.job_id, "title": r.title, "category": r.category,
        "category_es": CAT_ES.get(r.category, r.category), "tech_skills": r.tech_skills, "soft_skills": r.soft_skills,
        "min_years": r.min_years, "education_label": r.education_label, "weights": r.weights,
        "weights_updated_by": r.weights_updated_by, "summary": r.summary,
    }


def project_view(p: Project, with_roles: bool = True) -> dict:
    d = {"id": p.id, "code": p.code, "name": p.name, "area": p.area, "status": p.status,
         "description": p.description, "start": p.start, "end": p.end, "n_roles": len(p.roles)}
    if with_roles:
        d["roles"] = [role_view(r) for r in p.roles]
    return d


def candidate_summary(c: Candidate, best: Match | None) -> dict:
    name = decrypt(c.name_enc)
    return {
        "id": c.id, "code": c.code, "name": name,
        "initials": "".join(w[0] for w in name.split()[:2]).upper() or "TM",
        "headline": c.headline, "source_type": c.source_type, "years_experience": c.years_experience,
        "education_label": c.education_label, "n_tech": len(c.tech_skills), "n_soft": len(c.soft_skills),
        "created_at": c.created_at.isoformat() + "Z", "retention_until": c.retention_until.date().isoformat(),
        "edited": c.edited,
        "best": ({"role_id": best.role_id, "title": best.role.title, "project": best.role.project.name,
                  "score": best.score} if best else None),
    }


def candidate_profile(c: Candidate, reveal: bool = False) -> dict:
    email, phone = decrypt(c.email_enc), decrypt(c.phone_enc)
    base = candidate_summary(c, None)
    base.update({
        "email": email if reveal else mask_email(email), "phone": phone if reveal else mask_phone(phone),
        "location": decrypt(c.location_enc), "summary": c.summary, "tech_skills": c.tech_skills,
        "soft_skills": c.soft_skills, "experience": c.experience, "education": c.education,
        "education_level": c.education_level, "languages": c.languages, "certifications": c.certifications,
        "sensitive_discarded": c.sensitive_discarded, "quality": c.quality,
        "extraction_method": c.extraction_method,
        "consent": {"version": c.consent.policy_version, "purposes": c.consent.purposes,
                    "external_ai": c.consent.external_ai, "granted_at": c.consent.granted_at.isoformat() + "Z"},
    })
    return base


def match_view(m: Match) -> dict:
    r = m.role
    return {
        "role_id": r.id, "job_id": r.job_id, "title": r.title, "category": r.category,
        "category_es": CAT_ES.get(r.category, r.category), "project_id": r.project_id, "project": r.project.name,
        "score": m.score, "tech_score": m.tech_score, "soft_score": m.soft_score, "exp_score": m.exp_score,
        "edu_score": m.edu_score, "weights": m.weights, "matched_tech": m.matched_tech, "partial_tech": m.partial_tech,
        "missing_tech": m.missing_tech, "matched_soft": m.matched_soft, "missing_soft": m.missing_soft,
        "explanation": m.explanation, "rank": m.rank, "is_best": m.is_best, "viewed": m.viewed,
        "min_years": r.min_years, "education_label": r.education_label, "summary": r.summary,
    }


def plan_view(p: TrainingPlan | None) -> dict | None:
    if not p:
        return None
    groups: dict[str, dict] = {}
    for it in p.items:
        g = groups.setdefault(it.skill, {"skill": it.skill, "type": it.skill_type, "priority": it.priority, "courses": []})
        g["courses"].append({"platform": it.platform, "title": it.course_title, "provider": it.provider,
                             "rating": it.rating, "level": it.level, "hours": it.hours,
                             "hours_estimated": it.hours_estimated, "url": it.url})
    return {"id": p.id, "role_id": p.role_id, "total_hours": p.total_hours, "weeks": p.weeks,
            "projected_score": p.projected_score, "created_at": p.created_at.isoformat() + "Z",
            "n_courses": len(p.items), "skills": sorted(groups.values(), key=lambda g: g["priority"])}
