from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.database.models import (AuditLog, Candidate, Consent, HRDecision, MarketMatch, Match, PlanItem,
                                 ProjectMatch, Role, TrainingPlan)


class CandidateRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Candidatos -----------------------------------------------------
    def next_code(self) -> str:
        last = self.db.scalar(select(func.max(Candidate.id))) or 0
        return f"TM-{1001 + last:04d}"

    def by_id(self, cid: int) -> Candidate | None:
        return self.db.get(Candidate, cid)

    def by_hash(self, file_hash: str) -> Candidate | None:
        return self.db.scalar(select(Candidate).where(Candidate.file_hash == file_hash))

    def list(self) -> list[Candidate]:
        return list(self.db.scalars(select(Candidate).order_by(Candidate.created_at.desc())))

    def add(self, cand: Candidate) -> Candidate:
        self.db.add(cand)
        self.db.flush()
        return cand

    def delete(self, cand: Candidate) -> None:
        consent = cand.consent
        self.db.delete(cand)
        if consent:
            consent.revoked_at = datetime.utcnow()
        self.db.commit()

    def expired(self, now: datetime) -> list[Candidate]:
        return list(self.db.scalars(select(Candidate).where(Candidate.retention_until < now)))

    def add_consent(self, consent: Consent) -> Consent:
        self.db.add(consent)
        self.db.flush()
        return consent

    # --- Matches --------------------------------------------------------
    def replace_matches(self, cand: Candidate, matches: list[Match], projects: list[ProjectMatch],
                        market: list[MarketMatch]) -> None:
        self.db.execute(delete(Match).where(Match.candidate_id == cand.id))
        self.db.execute(delete(ProjectMatch).where(ProjectMatch.candidate_id == cand.id))
        self.db.execute(delete(MarketMatch).where(MarketMatch.candidate_id == cand.id))
        self.db.add_all(matches + projects + market)
        self.db.flush()

    def matches(self, cid: int) -> list[Match]:
        return list(self.db.scalars(select(Match).options(selectinload(Match.role).selectinload(Role.project))
                                    .where(Match.candidate_id == cid).order_by(Match.score.desc())))

    def match(self, cid: int, role_id: int) -> Match | None:
        return self.db.scalar(select(Match).where(Match.candidate_id == cid, Match.role_id == role_id))

    def project_matches(self, cid: int) -> list[ProjectMatch]:
        return list(self.db.scalars(select(ProjectMatch).where(ProjectMatch.candidate_id == cid).order_by(ProjectMatch.rank)))

    def market_matches(self, cid: int) -> list[MarketMatch]:
        return list(self.db.scalars(select(MarketMatch).where(MarketMatch.candidate_id == cid).order_by(MarketMatch.score.desc())))

    def best_match(self, cid: int) -> Match | None:
        return self.db.scalar(select(Match).where(Match.candidate_id == cid, Match.is_best.is_(True)))

    # --- Planes ---------------------------------------------------------
    def plan(self, cid: int, role_id: int) -> TrainingPlan | None:
        return self.db.scalar(select(TrainingPlan).options(selectinload(TrainingPlan.items))
                              .where(TrainingPlan.candidate_id == cid, TrainingPlan.role_id == role_id)
                              .order_by(TrainingPlan.created_at.desc()))

    def plans(self, cid: int) -> list[TrainingPlan]:
        return list(self.db.scalars(select(TrainingPlan).where(TrainingPlan.candidate_id == cid)))

    def save_plan(self, plan: TrainingPlan, items: list[PlanItem]) -> TrainingPlan:
        old = self.db.scalars(select(TrainingPlan).where(TrainingPlan.candidate_id == plan.candidate_id,
                                                         TrainingPlan.role_id == plan.role_id)).all()
        for o in old:
            self.db.delete(o)
        self.db.add(plan)
        self.db.flush()
        for it in items:
            it.plan_id = plan.id
        self.db.add_all(items)
        self.db.flush()
        return plan

    # --- Decisiones humanas ----------------------------------------------
    def add_decision(self, d: HRDecision) -> HRDecision:
        self.db.add(d)
        self.db.flush()
        return d

    def decisions(self, cid: int) -> list[HRDecision]:
        return list(self.db.scalars(select(HRDecision).where(HRDecision.candidate_id == cid).order_by(HRDecision.created_at.desc())))

    def commit(self) -> None:
        self.db.commit()


class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def log(self, user_email: str, action: str, entity: str = "", entity_ref: str = "", detail: str = "") -> None:
        self.db.add(AuditLog(user_email=user_email, action=action, entity=entity, entity_ref=entity_ref, detail=detail[:500]))
        self.db.commit()

    def recent(self, limit: int = 60) -> list[AuditLog]:
        return list(self.db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)))
