"""Orquestador del flujo: CV (PDF/JSON/imagen) → perfil → matching → plan de capacitación → BD."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.business.extraction.cv_parser import _scan_tech as scan_tech, experience_view, parse_text, total_years
from app.business.extraction.document_reader import read_image, read_pdf
from app.business.extraction.json_reader import read_json
from app.business.extraction.llm_extractor import enrich_with_claude
from app.business.extraction.sensitive import redact_sensitive
from app.business.matching_service import CandidateSkills, normalize_weights, quick_market_score, score_role
from app.business.privacy_service import register_consent
from app.business.skill_catalog import EDU_LEVELS, all_job_requirements, canonical_soft, canonical_tech, display_tech, soft_label
from app.business.text_utils import clean_display, norm
from app.business.training_service import build_plan
from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_MB, RETENTION_DAYS
from app.database.models import Candidate, HRDecision, MarketMatch, Match, PlanItem, ProjectMatch, Role, TrainingPlan, User
from app.persistence.crypto import encrypt
from app.persistence.datasets import trim_memory
from app.persistence.repositories.candidates import AuditRepository, CandidateRepository
from app.persistence.repositories.projects import ProjectRepository


class AnalysisError(Exception):
    pass


def role_dict(r: Role) -> dict:
    return {"id": r.id, "title": r.title, "category": r.category, "tech_skills": r.tech_skills,
            "soft_skills": r.soft_skills, "min_years": r.min_years, "education_level": r.education_level,
            "weights": r.weights}


def _skills_of(c: Candidate) -> CandidateSkills:
    return CandidateSkills.from_profile(c.tech_skills, c.soft_skills, c.years_experience, c.education_level)


# ---------------------------------------------------------------------------
# 1) Extracción
# ---------------------------------------------------------------------------
def extract_profile(filename: str, data: bytes, external_ai: bool) -> dict:
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AnalysisError("Formato no permitido. Use PDF (texto o escaneado), JSON o imagen PNG/JPG.")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise AnalysisError(f"El archivo supera el límite de {MAX_UPLOAD_MB} MB.")
    if not data:
        raise AnalysisError("El archivo está vacío.")

    declared: dict = {}
    sensitive: list[str] = []
    warnings: list[str] = []
    if ext == ".json":
        try:
            text, declared, sensitive = read_json(data)
        except ValueError as exc:
            raise AnalysisError(str(exc)) from exc
        source, method, ocr = "json", "Lectura estructurada de JSON", False
    elif ext == ".pdf":
        if not data.startswith(b"%PDF"):
            raise AnalysisError("El archivo no es un PDF válido.")
        rr = read_pdf(data)
        text, source, method, ocr = rr.text, rr.source_type, rr.method, rr.ocr_used
        warnings += rr.warnings
        if rr.photo_detected:
            sensitive.append("Fotografía")
    else:
        rr = read_image(data)
        text, source, method, ocr = rr.text, rr.source_type, rr.method, rr.ocr_used
        warnings += rr.warnings
    if len((text or "").strip()) < 40:
        raise AnalysisError("No fue posible leer contenido suficiente del documento. " + " ".join(warnings))

    clean_text, found = redact_sensitive(text)
    for f in found:
        if f not in sensitive:
            sensitive.append(f)
    profile = parse_text(clean_text, declared)
    if declared.get("contact"):
        for k, v in declared["contact"].items():
            if v:
                profile[k] = v
    if profile.get("references_omitted") and "Referencias de terceros" not in sensitive:
        sensitive.append("Referencias de terceros")

    ai_note = ""
    if external_ai:
        ai = enrich_with_claude(clean_text)
        ai_note = ai["note"]
        known_t = {s["key"] for s in profile["tech_skills"]}
        known_s = {s["key"] for s in profile["soft_skills"]}
        profile["tech_skills"] += [s for s in ai["tech"] if s["key"] not in known_t]
        profile["soft_skills"] += [s for s in ai["soft"] if s["key"] not in known_s]
        if ai["used"]:
            method += " + Claude API (evidencia verificada)"

    profile["quality"]["warnings"] = warnings + profile["quality"]["warnings"]
    if ai_note:
        profile["quality"]["ai_note"] = ai_note
    profile["quality"]["ocr_used"] = ocr
    return {"profile": profile, "source": source, "method": method, "sensitive": sensitive}


# ---------------------------------------------------------------------------
# 2) Matching y persistencia
# ---------------------------------------------------------------------------
def compute_and_store_matches(db: Session, cand: Candidate) -> None:
    projects = ProjectRepository(db)
    repo = CandidateRepository(db)
    skills = _skills_of(cand)
    roles = projects.roles()
    results = []
    for r in roles:
        res = score_role(skills, role_dict(r))
        results.append((r, res))
    results.sort(key=lambda x: -x[1]["score"])

    matches = []
    for rank, (r, res) in enumerate(results, start=1):
        matches.append(Match(candidate_id=cand.id, role_id=r.id, rank=rank, is_best=(rank == 1),
                             score=res["score"], tech_score=res["tech_score"], soft_score=res["soft_score"],
                             exp_score=res["exp_score"], edu_score=res["edu_score"], weights=res["weights"],
                             matched_tech=res["matched_tech"], partial_tech=res["partial_tech"],
                             missing_tech=res["missing_tech"], matched_soft=res["matched_soft"],
                             missing_soft=res["missing_soft"], explanation=res["explanation"]))
    by_project: dict[int, list] = {}
    for r, res in results:
        by_project.setdefault(r.project_id, []).append((r, res))
    proj_rows = []
    ordered = sorted(by_project.items(), key=lambda kv: -max(x[1]["score"] for x in kv[1]))
    for rank, (pid, items) in enumerate(ordered, start=1):
        best_r, best_res = max(items, key=lambda x: x[1]["score"])
        proj_rows.append(ProjectMatch(candidate_id=cand.id, project_id=pid, best_role_id=best_r.id, rank=rank,
                                      score=best_res["score"],
                                      avg_score=round(sum(x[1]["score"] for x in items) / len(items), 1)))
    # Movilidad ampliada: top 10 en todo el dataset (3.000 ofertas)
    project_jobs = {r.job_id for r in roles}
    market = []
    for req in all_job_requirements():
        sc, matched = quick_market_score(skills, req)
        if sc > 0:
            market.append((sc, req, matched))
    market.sort(key=lambda x: -x[0])
    # Re-puntuar los mejores candidatos con el motor completo para que la escala sea comparable
    from app.business.matching_service import default_weights
    rescored = []
    for _, req, matched in market[:40]:
        full = score_role(skills, {**req, "weights": default_weights(req["category"], req["title"])})
        rescored.append((full["score"], req, [m["name"] for m in full["matched_tech"]] or matched))
    rescored.sort(key=lambda x: -x[0])
    seen_titles: set[str] = set()
    market_rows = []
    for sc, req, matched in rescored:
        t = norm(req["title"])
        if t in seen_titles or req["job_id"] in project_jobs:
            continue
        seen_titles.add(t)
        market_rows.append(MarketMatch(candidate_id=cand.id, job_id=req["job_id"], title=req["title"],
                                       category=req["category"], score=sc, matched=matched[:8]))
        if len(market_rows) >= 10:
            break
    repo.replace_matches(cand, matches, proj_rows, market_rows)


def generate_plan(db: Session, cand: Candidate, role: Role, user: User) -> TrainingPlan:
    repo = CandidateRepository(db)
    m = repo.match(cand.id, role.id)
    res = match_to_result(m)
    plan_data = build_plan(res)
    plan = TrainingPlan(candidate_id=cand.id, role_id=role.id, total_hours=plan_data["total_hours"],
                        weeks=plan_data["weeks"], projected_score=plan_data["projected_score"], created_by=user.id)
    items = [PlanItem(**it) for it in plan_data["items"]]
    repo.save_plan(plan, items)
    return plan


def match_to_result(m: Match) -> dict:
    return {"score": m.score, "tech_score": m.tech_score, "soft_score": m.soft_score, "exp_score": m.exp_score,
            "edu_score": m.edu_score, "weights": m.weights, "matched_tech": m.matched_tech,
            "partial_tech": m.partial_tech, "missing_tech": m.missing_tech, "matched_soft": m.matched_soft,
            "missing_soft": m.missing_soft, "explanation": m.explanation}


def analyze_cv(db: Session, user: User, filename: str, data: bytes, consent_in: dict) -> tuple[Candidate, bool]:
    """Devuelve (candidato, es_duplicado)."""
    from app.business.bootstrap import ensure_warm

    ensure_warm()
    file_hash = hashlib.sha256(data).hexdigest()
    repo = CandidateRepository(db)
    audit = AuditRepository(db)
    existing = repo.by_hash(file_hash)
    if existing:
        audit.log(user.email, "cv_duplicado", "candidato", existing.code)
        return existing, True

    consent = register_consent(db, user, consent_in.get("purposes", []), consent_in.get("external_ai", False),
                               consent_in.get("attested", False))
    ex = extract_profile(filename, data, consent.external_ai)
    p = ex["profile"]
    cand = Candidate(
        code=repo.next_code(), name_enc=encrypt(p.get("name") or "Sin nombre identificado"),
        email_enc=encrypt(p.get("email")), phone_enc=encrypt(p.get("phone")), location_enc=encrypt(p.get("location")),
        headline=(p.get("headline") or "")[:200], summary=p.get("summary") or "", source_type=ex["source"],
        extraction_method=ex["method"][:60], file_hash=file_hash, years_experience=p["years_experience"],
        education_level=p["education_level"], education_label=p["education_label"], tech_skills=p["tech_skills"],
        soft_skills=p["soft_skills"], experience=p["experience"], education=p["education"], languages=p["languages"],
        certifications=p["certifications"], sensitive_discarded=ex["sensitive"], quality=p["quality"],
        consent_id=consent.id, created_by=user.id, retention_until=datetime.utcnow() + timedelta(days=RETENTION_DAYS),
    )
    repo.add(cand)
    compute_and_store_matches(db, cand)
    best = repo.best_match(cand.id)
    if best and "capacitacion" in consent.purposes:
        generate_plan(db, cand, best.role, user)
    repo.commit()
    audit.log(user.email, "cv_analizado", "candidato", cand.code,
              f"Fuente: {ex['source']}; sensibles descartados: {len(ex['sensitive'])}")
    trim_memory()
    return cand, False


# ---------------------------------------------------------------------------
# 3) Edición del perfil (rectificación) y re-cálculo
# ---------------------------------------------------------------------------
def update_profile(db: Session, user: User, cand: Candidate, payload: dict) -> Candidate:
    def mk_tech(names):
        out, seen = [], set()
        prev = {s["key"]: s for s in cand.tech_skills}
        for n in names:
            n = clean_display(n)
            if not n:
                continue
            k = canonical_tech(n)
            if k in seen:
                continue
            seen.add(k)
            out.append(prev.get(k) or {"key": k, "name": display_tech(k) if len(k) > 1 else n, "confidence": 1.0,
                                       "evidence": "Agregada/validada por Talento Humano", "source": "Edición manual"})
        return out

    def mk_soft(names):
        out, seen = [], set()
        prev = {s["key"]: s for s in cand.soft_skills}
        for n in names:
            n = clean_display(n)
            if not n:
                continue
            k = canonical_soft(n) or norm(n)
            if k in seen:
                continue
            seen.add(k)
            out.append(prev.get(k) or {"key": k, "name": soft_label(k) if canonical_soft(n) else n, "confidence": 1.0,
                                       "evidence": "Agregada/validada por Talento Humano", "source": "Edición manual"})
        return out

    if "tech_skills" in payload:
        cand.tech_skills = mk_tech(payload["tech_skills"])
    if "soft_skills" in payload:
        cand.soft_skills = mk_soft(payload["soft_skills"])
    changed = [k for k in ("tech_skills", "soft_skills", "experience", "education", "certifications",
                           "years_experience", "education_level", "headline", "name") if k in payload]
    if "experience" in payload:
        entries = _normalize_experience(payload["experience"])
        cand.experience = [experience_view(e) for e in entries]
        computed = total_years([e for e in entries if e["start"]])
        if "years_experience" not in payload:
            cand.years_experience = computed
    if "years_experience" in payload:
        cand.years_experience = max(0.0, min(50.0, float(payload["years_experience"] or 0)))
    if "education" in payload:
        cand.education = _normalize_education(payload["education"])
        if "education_level" not in payload:
            lvl = max([e["level"] for e in cand.education] or [0])
            cand.education_level, cand.education_label = lvl, EDU_LEVELS[lvl]
    if "education_level" in payload:
        lvl = int(payload["education_level"] or 0)
        cand.education_level = lvl if lvl in EDU_LEVELS else 0
        cand.education_label = EDU_LEVELS[cand.education_level]
    if "certifications" in payload:
        cand.certifications = _normalize_certs(payload["certifications"])
        cand.tech_skills = _skills_from_certs(cand.certifications, cand.tech_skills)
    if payload.get("headline") is not None:
        cand.headline = clean_display(payload["headline"])[:200]
    if payload.get("name"):
        cand.name_enc = encrypt(clean_display(payload["name"])[:120])
    cand.edited = True
    db.flush()
    compute_and_store_matches(db, cand)
    best = CandidateRepository(db).best_match(cand.id)
    for plan in CandidateRepository(db).plans(cand.id):
        db.delete(plan)
    db.flush()
    if best and "capacitacion" in cand.consent.purposes:
        generate_plan(db, cand, best.role, user)
    db.commit()
    AuditRepository(db).log(user.email, "perfil_rectificado", "candidato", cand.code,
                            "Secciones: " + ", ".join(changed))
    return cand


def _parse_ym(value) -> int:
    if not value:
        return 0
    m = re.match(r"^\s*(\d{4})-(\d{1,2})\s*$", str(value))
    if not m:
        raise AnalysisError(f"Fecha inválida: {value}. Use el formato AAAA-MM.")
    y, mo = int(m.group(1)), int(m.group(2))
    if not (1960 <= y <= 2100 and 1 <= mo <= 12):
        raise AnalysisError(f"Fecha fuera de rango: {value}.")
    return y * 12 + mo


def _normalize_experience(items: list) -> list[dict]:
    """Experiencia editada por Talento Humano (p. ej. ascensos internos) → entradas con índices de mes."""
    today = datetime.utcnow()
    now_idx = today.year * 12 + today.month
    out = []
    for it in items[:30]:
        role = clean_display(it.get("role", ""))[:140]
        company = clean_display(it.get("company", ""))[:120]
        if not role and not company:
            continue
        start = _parse_ym(it.get("start"))
        end = now_idx if it.get("current") else _parse_ym(it.get("end"))
        if start and start > now_idx:
            raise AnalysisError(f"La fecha de inicio de «{role or company}» está en el futuro.")
        if start and end and end < start:
            raise AnalysisError(f"En «{role or company}» la fecha de fin es anterior a la de inicio.")
        if start and not end:
            end = start
        years = round((end - start) / 12, 1) if start else float(it.get("years") or 0)
        period = ""
        if start:
            period = f"{(start - 1) % 12 + 1:02d}/{(start - 1) // 12} – " + (
                "Actual" if it.get("current") else f"{(end - 1) % 12 + 1:02d}/{(end - 1) // 12}")
        out.append({"role": role, "company": company, "start": start, "end": end, "years": years, "period": period,
                    "source": clean_display(it.get("source", "")) or "Edición manual"})
    out.sort(key=lambda e: -(e["end"] or 0))
    return out


def _normalize_education(items: list) -> list[dict]:
    out = []
    for it in items[:20]:
        title = clean_display(it.get("title", "") or it.get("text", ""))[:160]
        inst = clean_display(it.get("institution", ""))[:120]
        if not title and not inst:
            continue
        lvl = int(it.get("level") or 0)
        lvl = lvl if lvl in EDU_LEVELS else 0
        status = clean_display(it.get("status", ""))[:40]
        text = " - ".join(x for x in [title, inst] if x) + (f" ({status})" if status else "")
        out.append({"text": text[:200], "title": title, "institution": inst, "level": lvl, "status": status})
    return out


def _normalize_certs(items: list) -> list[dict]:
    out = []
    for it in items[:40]:
        if isinstance(it, str):
            it = {"name": it}
        name = clean_display(it.get("name", ""))[:160]
        if not name:
            continue
        year = it.get("year")
        try:
            year = int(year) if year not in (None, "") else None
        except (TypeError, ValueError):
            year = None
        if year is not None and not (1970 <= year <= datetime.utcnow().year + 1):
            raise AnalysisError(f"Año inválido para la certificación «{name}».")
        out.append({"name": name, "issuer": clean_display(it.get("issuer", ""))[:120], "year": year,
                    "internal": bool(it.get("internal"))})
    return out


def _skills_from_certs(certs: list[dict], tech: list[dict]) -> list[dict]:
    """Una certificación (interna o externa) evidencia las tecnologías que nombra (p. ej. 'AWS', 'Kubernetes')."""
    found: dict = {}
    for c in certs:
        scan_tech(f"{c['name']} {c.get('issuer', '')}", found, in_skills=True)
    known = {s["key"] for s in tech}
    added = []
    for key, s in found.items():
        if key in known:
            continue
        cert = next((c for c in certs if norm(s["name"]) in norm(c["name"] + " " + c.get("issuer", ""))), None)
        label = cert["name"] if cert else s["evidence"]
        added.append({**s, "confidence": 0.95, "evidence": f"Certificación: {label}",
                      "source": "Certificación interna" if cert and cert.get("internal") else "Certificación"})
    return tech + added


def reweight_role(db: Session, user: User, cand: Candidate, role: Role, weights: dict, apply_to_role: bool) -> Match:
    """Ponderación dinámica: recalcula el cargo con los pesos dados y guarda el resultado."""
    w = normalize_weights({**weights, "naturaleza": role.weights.get("naturaleza", "Ajustado por Talento Humano")})
    if apply_to_role:
        role.weights = w
        role.weights_updated_by = user.email
        db.flush()
        for m in list(db.query(Match).filter(Match.role_id == role.id)):
            c = m.candidate
            res = score_role(_skills_of(c), role_dict(role), w)
            _apply(m, res)
    m = CandidateRepository(db).match(cand.id, role.id)
    res = score_role(_skills_of(cand), role_dict(role), w)
    _apply(m, res)
    _rerank(db, cand)
    db.commit()
    AuditRepository(db).log(user.email, "ponderacion_ajustada", "cargo", str(role.job_id),
                            f"{'Perfil del cargo' if apply_to_role else 'Sólo este análisis'}: "
                            + ", ".join(f"{k}={v:.2f}" for k, v in w.items() if k != "naturaleza"))
    return m


def _apply(m: Match, res: dict) -> None:
    for k in ("score", "tech_score", "soft_score", "exp_score", "edu_score", "weights", "matched_tech", "partial_tech",
              "missing_tech", "matched_soft", "missing_soft", "explanation"):
        setattr(m, k, res[k])


def _rerank(db: Session, cand: Candidate) -> None:
    repo = CandidateRepository(db)
    ms = sorted(repo.matches(cand.id), key=lambda x: -x.score)
    for i, m in enumerate(ms, start=1):
        m.rank, m.is_best = i, i == 1
    for pm in repo.project_matches(cand.id):
        items = [m for m in ms if m.role.project_id == pm.project_id]
        if items:
            best = max(items, key=lambda x: x.score)
            pm.best_role_id, pm.score = best.role_id, best.score
            pm.avg_score = round(sum(i.score for i in items) / len(items), 1)
    for i, pm in enumerate(sorted(repo.project_matches(cand.id), key=lambda x: -x.score), start=1):
        pm.rank = i


def record_decision(db: Session, user: User, cand: Candidate, role: Role, decision: str, justification: str) -> HRDecision:
    if decision not in {"asignar", "en_revision", "descartar"}:
        raise AnalysisError("Decisión no válida.")
    if len(clean_display(justification)) < 15:
        raise AnalysisError("La justificación humana es obligatoria (mínimo 15 caracteres).")
    m = CandidateRepository(db).match(cand.id, role.id)
    d = HRDecision(candidate_id=cand.id, role_id=role.id, decision=decision, justification=clean_display(justification),
                   score_at_decision=m.score if m else 0, user_id=user.id)
    CandidateRepository(db).add_decision(d)
    db.commit()
    AuditRepository(db).log(user.email, "decision_humana", "candidato", cand.code, f"{decision} → cargo {role.job_id}")
    return d
