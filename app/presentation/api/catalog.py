from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.business.insights_service import dataset_insights
from app.database.connection import get_db
from app.database.models import User
from app.persistence.repositories.candidates import CandidateRepository
from app.persistence.repositories.projects import ProjectRepository
from app.presentation.dependencies import current_user
from app.presentation.serializers import project_view

router = APIRouter(prefix="/api", tags=["Catálogo"])


@router.get("/projects")
def projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"projects": [project_view(p) for p in ProjectRepository(db).all_with_roles()]}


@router.get("/insights")
def insights(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.business.bootstrap import ensure_warm

    ensure_warm()
    data = dict(dataset_insights())
    repo = CandidateRepository(db)
    cands = repo.list()
    bests = [b.score for b in (repo.best_match(c.id) for c in cands) if b]
    data["bank"] = {"cvs": len(cands), "avg_best": round(sum(bests) / len(bests), 1) if bests else 0,
                    "plans": sum(len(repo.plans(c.id)) for c in cands),
                    "projects": len(ProjectRepository(db).all_with_roles()), "roles": len(ProjectRepository(db).roles())}
    return data
