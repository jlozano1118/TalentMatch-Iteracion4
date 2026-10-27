from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.business import analysis_service as svc
from app.business.privacy_service import delete_candidate, export_candidate
from app.config import MAX_UPLOAD_MB
from app.database.connection import get_db
from app.database.models import User
from app.persistence.repositories.candidates import AuditRepository, CandidateRepository
from app.persistence.repositories.projects import ProjectRepository
from app.presentation.dependencies import candidate_or_404, current_user
from app.presentation.serializers import candidate_profile, candidate_summary, match_view, plan_view, project_view

router = APIRouter(prefix="/api/candidates", tags=["Hojas de vida"])


def _full_result(db: Session, cid: int) -> dict:
    repo = CandidateRepository(db)
    cand = candidate_or_404(cid, db)
    matches = repo.matches(cid)
    pm = repo.project_matches(cid)
    projects = {p.id: p for p in ProjectRepository(db).all_with_roles()}
    by_project: dict[int, list] = {}
    for m in matches:
        by_project.setdefault(m.role.project_id, []).append(match_view(m))
    best = repo.best_match(cid)
    plan = repo.plan(cid, best.role_id) if best else None
    return {
        "candidate": candidate_profile(cand),
        "best": match_view(best) if best else None,
        "projects": [{**project_view(projects[x.project_id], with_roles=False), "score": x.score, "avg_score": x.avg_score,
                      "rank": x.rank, "best_role_id": x.best_role_id,
                      "roles": sorted(by_project.get(x.project_id, []), key=lambda r: -r["score"])} for x in pm],
        "market": [{"job_id": m.job_id, "title": m.title, "category": m.category, "score": m.score, "matched": m.matched}
                   for m in repo.market_matches(cid)],
        "plan": plan_view(plan),
        "decisions": [{"role_id": d.role_id, "decision": d.decision, "justification": d.justification,
                       "score": d.score_at_decision, "created_at": d.created_at.isoformat() + "Z"} for d in repo.decisions(cid)],
    }


@router.post("/analyze")
def analyze(file: UploadFile = File(...), consent: str = Form(...), user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    try:
        consent_in = json.loads(consent)
    except json.JSONDecodeError:
        raise HTTPException(400, "Consentimiento inválido.")
    data = file.file.read(MAX_UPLOAD_MB * 1024 * 1024 + 1)
    try:
        cand, duplicate = svc.analyze_cv(db, user, file.filename or "", data, consent_in)
    except (svc.AnalysisError, ValueError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    result = _full_result(db, cand.id)
    result["duplicate"] = duplicate
    return result


@router.get("")
def bank(user: User = Depends(current_user), db: Session = Depends(get_db)):
    repo = CandidateRepository(db)
    return {"candidates": [candidate_summary(c, repo.best_match(c.id)) for c in repo.list()]}


@router.get("/{cid}")
def detail(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    AuditRepository(db).log(user.email, "consulta_perfil", "candidato", candidate_or_404(cid, db).code)
    return _full_result(db, cid)


@router.get("/{cid}/contact")
def reveal_contact(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cand = candidate_or_404(cid, db)
    AuditRepository(db).log(user.email, "ver_datos_contacto", "candidato", cand.code)
    p = candidate_profile(cand, reveal=True)
    return {"email": p["email"], "phone": p["phone"]}


class ExperienceIn(BaseModel):
    role: str = Field(default="", max_length=160)
    company: str = Field(default="", max_length=120)
    start: str | None = Field(default=None, max_length=7)
    end: str | None = Field(default=None, max_length=7)
    current: bool = False
    years: float | None = Field(default=None, ge=0, le=50)
    source: str | None = Field(default=None, max_length=60)


class EducationIn(BaseModel):
    title: str = Field(default="", max_length=200)
    institution: str = Field(default="", max_length=120)
    level: int = Field(default=0, ge=0, le=7)
    status: str = Field(default="", max_length=40)


class CertificationIn(BaseModel):
    name: str = Field(max_length=160)
    issuer: str = Field(default="", max_length=120)
    year: int | None = None
    internal: bool = False


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    headline: str | None = Field(default=None, max_length=200)
    tech_skills: list[str] | None = None
    soft_skills: list[str] | None = None
    years_experience: float | None = Field(default=None, ge=0, le=50)
    education_level: int | None = Field(default=None, ge=0, le=7)
    experience: list[ExperienceIn] | None = Field(default=None, max_length=30)
    education: list[EducationIn] | None = Field(default=None, max_length=20)
    certifications: list[CertificationIn] | None = Field(default=None, max_length=40)


@router.put("/{cid}/profile")
def edit_profile(cid: int, body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cand = candidate_or_404(cid, db)
    try:
        svc.update_profile(db, user, cand, body.model_dump(exclude_none=True))
    except svc.AnalysisError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    return _full_result(db, cid)


@router.get("/{cid}/roles/{role_id}")
def role_detail(cid: int, role_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Al dar clic en un cargo se registra la consulta y se genera/guarda su plan de capacitación."""
    cand = candidate_or_404(cid, db)
    role = ProjectRepository(db).role(role_id)
    if not role:
        raise HTTPException(404, "Cargo no encontrado.")
    repo = CandidateRepository(db)
    m = repo.match(cid, role_id)
    if not m:
        raise HTTPException(404, "No hay análisis para este cargo.")
    m.viewed = True
    plan = repo.plan(cid, role_id)
    if plan is None and "capacitacion" in cand.consent.purposes:
        svc.generate_plan(db, cand, role, user)
        plan = repo.plan(cid, role_id)
    db.commit()
    AuditRepository(db).log(user.email, "consulta_cargo", "candidato", cand.code, f"Cargo {role.job_id}")
    return {"match": match_view(m), "plan": plan_view(plan), "role": {"weights_default": role.weights,
                                                                      "weights_updated_by": role.weights_updated_by}}


class WeightsIn(BaseModel):
    tecnico: float = Field(ge=0, le=1)
    power: float = Field(ge=0, le=1)
    experiencia: float = Field(ge=0, le=1)
    educacion: float = Field(ge=0, le=1)
    apply_to_role: bool = False


@router.post("/{cid}/roles/{role_id}/weights")
def reweight(cid: int, role_id: int, body: WeightsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cand = candidate_or_404(cid, db)
    role = ProjectRepository(db).role(role_id)
    if not role:
        raise HTTPException(404, "Cargo no encontrado.")
    if body.tecnico + body.power + body.experiencia + body.educacion <= 0:
        raise HTTPException(422, "Al menos un peso debe ser mayor a cero.")
    svc.reweight_role(db, user, cand, role, body.model_dump(exclude={"apply_to_role"}), body.apply_to_role)
    if "capacitacion" in cand.consent.purposes:
        svc.generate_plan(db, cand, role, user)
        db.commit()
    return role_detail(cid, role_id, user, db)


class DecisionIn(BaseModel):
    decision: str
    justification: str = Field(min_length=1, max_length=1000)


@router.post("/{cid}/roles/{role_id}/decision")
def decision(cid: int, role_id: int, body: DecisionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cand = candidate_or_404(cid, db)
    role = ProjectRepository(db).role(role_id)
    if not role:
        raise HTTPException(404, "Cargo no encontrado.")
    try:
        svc.record_decision(db, user, cand, role, body.decision, body.justification)
    except svc.AnalysisError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"ok": True}


@router.get("/{cid}/export")
def export(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cand = candidate_or_404(cid, db)
    data = export_candidate(db, cand, user)
    return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="habeas-data-{cand.code}.json"'})


class DeleteIn(BaseModel):
    reason: str = Field(default="Solicitud del titular", max_length=300)


@router.post("/{cid}/delete")
def remove(cid: int, body: DeleteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    cand = candidate_or_404(cid, db)
    delete_candidate(db, cand, user, body.reason)
    return {"ok": True}
