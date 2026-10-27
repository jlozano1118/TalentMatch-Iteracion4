"""Modelo relacional (ORM) de TalentMatch.

Principios aplicados:
- Datos de contacto cifrados en reposo (columnas *_enc).
- Seudonimización: el matching y el banco usan el código TM-XXXX.
- Borrado en cascada para el derecho de supresión (Ley 1581 art. 8e / RGPD art. 17).
- Bitácora de auditoría sin datos personales (AI Act art. 12: registro de eventos).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


def _now() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(40), default="Analista de Talento Humano")
    password_hash: Mapped[str] = mapped_column(String(120))
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    area: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    start: Mapped[str] = mapped_column(String(20))
    end: Mapped[str] = mapped_column(String(20))
    roles: Mapped[list["Role"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Role(Base):
    """Cargo de un proyecto. Sus requisitos provienen de JobsDatasetProcessed.csv (columna ID)."""

    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    job_id: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(80))
    tech_skills: Mapped[list] = mapped_column(JSON, default=list)
    soft_skills: Mapped[list] = mapped_column(JSON, default=list)
    min_years: Mapped[float] = mapped_column(Float, default=0)
    education_level: Mapped[int] = mapped_column(Integer, default=0)
    education_label: Mapped[str] = mapped_column(String(80), default="No especificado")
    weights: Mapped[dict] = mapped_column(JSON, default=dict)
    weights_updated_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    project: Mapped[Project] = relationship(back_populates="roles")


class Consent(Base):
    """Autorización previa, expresa e informada del titular (Ley 1581 art. 9)."""

    __tablename__ = "consents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_version: Mapped[str] = mapped_column(String(40))
    purposes: Mapped[list] = mapped_column(JSON, default=list)
    external_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    channel: Mapped[str] = mapped_column(String(60), default="Formulario TalentMatch")
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name_enc: Mapped[str] = mapped_column(Text)
    email_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    headline: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(20))          # pdf-texto | pdf-escaneado | imagen | json
    extraction_method: Mapped[str] = mapped_column(String(60))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)  # sólo huella SHA-256, no el archivo
    years_experience: Mapped[float] = mapped_column(Float, default=0)
    education_level: Mapped[int] = mapped_column(Integer, default=0)
    education_label: Mapped[str] = mapped_column(String(80), default="No identificado")
    tech_skills: Mapped[list] = mapped_column(JSON, default=list)   # [{name, confidence, evidence, source}]
    soft_skills: Mapped[list] = mapped_column(JSON, default=list)
    experience: Mapped[list] = mapped_column(JSON, default=list)
    education: Mapped[list] = mapped_column(JSON, default=list)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    certifications: Mapped[list] = mapped_column(JSON, default=list)
    sensitive_discarded: Mapped[list] = mapped_column(JSON, default=list)  # sólo categorías, nunca valores
    quality: Mapped[dict] = mapped_column(JSON, default=dict)
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_id: Mapped[int] = mapped_column(ForeignKey("consents.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    retention_until: Mapped[datetime] = mapped_column(DateTime)

    matches: Mapped[list["Match"]] = relationship(back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True)
    project_matches: Mapped[list["ProjectMatch"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    market_matches: Mapped[list["MarketMatch"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    plans: Mapped[list["TrainingPlan"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    decisions: Mapped[list["HRDecision"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    consent: Mapped[Consent] = relationship()


class Match(Base):
    """Compatibilidad candidato ↔ cargo (se guardan TODOS los cargos de TODOS los proyectos)."""

    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(Float)
    tech_score: Mapped[float] = mapped_column(Float)
    soft_score: Mapped[float] = mapped_column(Float)
    exp_score: Mapped[float] = mapped_column(Float)
    edu_score: Mapped[float] = mapped_column(Float)
    weights: Mapped[dict] = mapped_column(JSON)
    matched_tech: Mapped[list] = mapped_column(JSON, default=list)
    partial_tech: Mapped[list] = mapped_column(JSON, default=list)
    missing_tech: Mapped[list] = mapped_column(JSON, default=list)
    matched_soft: Mapped[list] = mapped_column(JSON, default=list)
    missing_soft: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[list] = mapped_column(JSON, default=list)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    is_best: Mapped[bool] = mapped_column(Boolean, default=False)
    viewed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    candidate: Mapped[Candidate] = relationship(back_populates="matches")
    role: Mapped[Role] = relationship()


class ProjectMatch(Base):
    __tablename__ = "project_matches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    best_role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(Float)
    avg_score: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)


class MarketMatch(Base):
    """Top de cargos compatibles en todo el dataset (3.000 ofertas) — movilidad más allá de los proyectos."""

    __tablename__ = "market_matches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(80))
    score: Mapped[float] = mapped_column(Float)
    matched: Mapped[list] = mapped_column(JSON, default=list)


class TrainingPlan(Base):
    __tablename__ = "training_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    total_hours: Mapped[float] = mapped_column(Float, default=0)
    weeks: Mapped[int] = mapped_column(Integer, default=0)
    projected_score: Mapped[float] = mapped_column(Float, default=0)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    items: Mapped[list["PlanItem"]] = relationship(cascade="all, delete-orphan", passive_deletes=True, order_by="PlanItem.priority")


class PlanItem(Base):
    __tablename__ = "plan_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id", ondelete="CASCADE"), index=True)
    skill: Mapped[str] = mapped_column(String(160))
    skill_type: Mapped[str] = mapped_column(String(20))   # tecnica | power
    priority: Mapped[int] = mapped_column(Integer)
    platform: Mapped[str] = mapped_column(String(20))     # Coursera | Udemy
    course_title: Mapped[str] = mapped_column(String(300))
    provider: Mapped[str] = mapped_column(String(200))
    rating: Mapped[float] = mapped_column(Float)
    level: Mapped[str] = mapped_column(String(40))
    hours: Mapped[float] = mapped_column(Float)
    hours_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[str] = mapped_column(String(500))
    relevance: Mapped[float] = mapped_column(Float)


class HRDecision(Base):
    """Supervisión humana: la IA recomienda, una persona decide y justifica (AI Act art. 14)."""

    __tablename__ = "hr_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    decision: Mapped[str] = mapped_column(String(30))
    justification: Mapped[str] = mapped_column(Text)
    score_at_decision: Mapped[float] = mapped_column(Float)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_email: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity: Mapped[str] = mapped_column(String(40), default="")
    entity_ref: Mapped[str] = mapped_column(String(40), default="")   # código seudónimo, nunca el nombre
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
