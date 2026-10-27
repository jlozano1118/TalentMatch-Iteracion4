"""Arranque: esquema, usuarios autorizados, proyectos/cargos desde el dataset y retención."""
from __future__ import annotations

import logging
import threading

from sqlalchemy import select

from app.business.matching_service import default_weights
from app.business.privacy_service import purge_expired
from app.business.skill_catalog import all_job_requirements, parse_job_requirements
from app.database.connection import session_scope
from app.database.init_db import AUTHORIZED_USERS, create_schema
from app.database.models import Project, Role, User
from app.database.projects_catalog import PROJECTS
from app.persistence.datasets import dataset_stats, load_jobs, release_memory

log = logging.getLogger("talentmatch.bootstrap")


def _sync_users(db) -> None:
    allowed = {u["email"] for u in AUTHORIZED_USERS}
    for existing in db.scalars(select(User)).all():
        if existing.email not in allowed:          # sólo las cuentas autorizadas pueden existir
            db.delete(existing)
    for u in AUTHORIZED_USERS:
        user = db.scalar(select(User).where(User.email == u["email"]))
        if user is None:
            db.add(User(**u))
        else:
            user.password_hash = u["password_hash"]
            user.display_name = u["display_name"]


def _sync_projects(db) -> None:
    if db.scalar(select(Project.id).limit(1)):
        return
    jobs = load_jobs()
    for p in PROJECTS:
        proj = Project(code=p["code"], name=p["name"], area=p["area"], status=p["status"],
                       description=p["description"], start=p["start"], end=p["end"])
        db.add(proj)
        db.flush()
        for jid in p["job_ids"]:
            if jid not in jobs.index:
                log.warning("El cargo %s no existe en el dataset; se omite", jid)
                continue
            req = parse_job_requirements(jobs.loc[jid])
            db.add(Role(project_id=proj.id, job_id=req["job_id"], title=req["title"], category=req["category"],
                        tech_skills=req["tech_skills"], soft_skills=req["soft_skills"], min_years=req["min_years"],
                        education_level=req["education_level"], education_label=req["education_label"],
                        weights=default_weights(req["category"], req["title"]), summary=req["summary"]))


_WARM_LOCK = threading.Lock()
_WARM_DONE = threading.Event()


def ensure_warm() -> None:
    """Carga los datasets UNA sola vez aunque varias peticiones lleguen a la vez (evita duplicar memoria)."""
    if _WARM_DONE.is_set():
        return
    with _WARM_LOCK:
        if _WARM_DONE.is_set():
            return
        from app.business.training_service import _index
        from app.business.insights_service import dataset_insights

        dataset_stats()          # se calcula antes de liberar los DataFrames crudos
        _index()
        all_job_requirements()
        dataset_insights()
        release_memory()
        _WARM_DONE.set()
        log.info("Cachés de datasets listas y memoria liberada")


def _warm_caches() -> None:
    try:
        ensure_warm()
        import os

        if os.getenv("TM_WARM_BENCHMARK", "true").lower() == "true":
            from app.business.evaluation_service import extraction_benchmark

            extraction_benchmark()
            log.info("Banco de pruebas de extracción calculado")
    except Exception as exc:  # pragma: no cover
        log.error("Error precargando datasets: %s", exc)


def init_app(warm_in_background: bool = True) -> None:
    create_schema()
    with session_scope() as db:
        _sync_users(db)
        _sync_projects(db)
    with session_scope() as db:
        n = purge_expired(db)
        if n:
            log.info("Retención: %s hojas de vida eliminadas por vencimiento", n)
    if warm_in_background:
        threading.Thread(target=_warm_caches, daemon=True).start()
    else:
        _warm_caches()
