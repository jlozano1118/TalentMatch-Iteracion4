from __future__ import annotations

import threading

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.business.evaluation_service import extraction_benchmark, live_metrics
from app.business.extraction.document_reader import ocr_available
from app.business.privacy_service import POLICY
from app.config import EXTERNAL_AI_ENABLED
from app.database.connection import get_db
from app.database.models import User
from app.persistence.repositories.candidates import AuditRepository
from app.presentation.dependencies import current_user

router = APIRouter(prefix="/api", tags=["Ética y privacidad"])
_bench_lock = threading.Lock()
_bench_state = {"running": False}


@router.get("/privacy/policy")
def policy(user: User = Depends(current_user)):
    return {**POLICY, "external_ai_available": EXTERNAL_AI_ENABLED, "ocr_available": ocr_available()}


def _run_bench():
    try:
        extraction_benchmark()
    finally:
        _bench_state["running"] = False


@router.get("/ethics")
def ethics(user: User = Depends(current_user), db: Session = Depends(get_db)):
    bench = None
    if extraction_benchmark.cache_info().currsize:
        bench = extraction_benchmark()
    else:
        with _bench_lock:
            if not _bench_state["running"]:
                _bench_state["running"] = True
                threading.Thread(target=_run_bench, daemon=True).start()
    return {"live": live_metrics(db), "benchmark": bench, "benchmark_running": bench is None,
            "external_ai": EXTERNAL_AI_ENABLED, "ocr": ocr_available()}


@router.get("/audit")
def audit(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"events": [{"when": e.created_at.isoformat() + "Z", "user": e.user_email, "action": e.action,
                        "entity": e.entity, "ref": e.entity_ref, "detail": e.detail}
                       for e in AuditRepository(db).recent()]}
