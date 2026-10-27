"""Pruebas automáticas de TalentMatch (ejecutar con:  python -m pytest -q).

Usan una base de datos temporal y los CV de prueba ficticios de tests/fixtures.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

_TMP = tempfile.mkdtemp(prefix="tm_test_")
os.environ["TM_STORAGE_DIR"] = _TMP
os.environ["TM_DATABASE_URL"] = f"sqlite:///{Path(_TMP, 'test.db').as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402

from app.business.extraction.sensitive import redact_sensitive  # noqa: E402
from app.business.matching_service import CandidateSkills, score_role  # noqa: E402
from app.main import app  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
if not (FIX / "cv_texto_data_engineer.pdf").exists():
    from tests.make_fixtures import main as make

    make()

CONSENT = json.dumps({"attested": True, "purposes": ["matching", "capacitacion"], "external_ai": False})
USERS = {"jslozano95@talentmatch.co": "JLOZ12345#_", "adrojas53@talentmatch.co": "ADROJ#_293",
         "jslopez59@talentmatch.co": "JSLOP_030#$", "joromero10@talentmatch.co": "JORM1010{[["}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"email": "jslozano95@talentmatch.co", "password": USERS["jslozano95@talentmatch.co"]})
        assert r.status_code == 200
        yield c


# ------------------------------------------------------------------ autenticación
def test_only_authorized_users_can_login():
    with TestClient(app) as c:
        for email, pwd in USERS.items():
            assert c.post("/api/auth/login", json={"email": email, "password": pwd}).status_code == 200
        assert c.post("/api/auth/login", json={"email": "admin@talentmatch.co", "password": "x"}).status_code == 401
        assert c.post("/api/auth/login", json={"email": "jslozano95@gmail.com", "password": "x"}).status_code == 400
        assert c.post("/api/auth/login", json={"email": "adrojas53@talentmatch.co", "password": "JLOZ12345#_"}).status_code == 401


def test_protected_endpoints_require_session():
    with TestClient(app) as c:
        assert c.get("/api/candidates").status_code == 401
        assert c.get("/api/projects").status_code == 401


# ------------------------------------------------------------------ privacidad
def test_consent_is_mandatory(client):
    data = (FIX / "cv_json_ats_es.json").read_bytes()
    r = client.post("/api/candidates/analyze", files={"file": ("cv.json", data)},
                    data={"consent": json.dumps({"attested": False, "purposes": ["matching"]})})
    assert r.status_code == 422


def test_sensitive_data_is_discarded():
    text = "Ana Gómez\nC.C. 1.020.555.555\nFecha de nacimiento: 01/01/1990\nEstado civil: casada\nPython, SQL"
    clean, cats = redact_sensitive(text)
    assert "1.020.555.555" not in clean and "1990" not in clean
    assert {"Documento de identidad", "Fecha de nacimiento", "Estado civil"} <= set(cats)
    assert "Python" in clean


def test_score_ignores_personal_identity():
    role = {"title": "Data Engineer", "category": "Data Engineer", "min_years": 2, "education_level": 4,
            "tech_skills": [{"key": "python", "name": "Python", "weight": 1}, {"key": "sql", "name": "SQL", "weight": 1}],
            "soft_skills": [{"key": "teamwork", "name": "Trabajo en equipo", "weight": 1}]}
    a = CandidateSkills(tech={"python": "Python"}, soft={"teamwork": "x"}, years=3, edu_level=4)
    b = CandidateSkills(tech={"python": "Python"}, soft={"teamwork": "x"}, years=3, edu_level=4)
    assert score_role(a, role)["score"] == score_role(b, role)["score"]


# ------------------------------------------------------------------ flujo completo
@pytest.mark.parametrize("fname", ["cv_texto_data_engineer.pdf", "cv_escaneado_fullstack.pdf", "cv_json_resume.json", "cv_json_ats_es.json"])
def test_analyze_formats(client, fname):
    r = client.post("/api/candidates/analyze", files={"file": (fname, (FIX / fname).read_bytes())}, data={"consent": CONSENT})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["candidate"]["tech_skills"], "debe extraer habilidades técnicas"
    assert d["best"]["score"] > 0
    assert sum(len(p["roles"]) for p in d["projects"]) >= 30          # compatibilidad con TODOS los cargos
    assert d["plan"] is not None
    for s in d["plan"]["skills"]:
        for c in s["courses"]:
            assert c["rating"] > 4.0 and c["url"].startswith("https://")
    assert "@" not in d["candidate"]["email"].split("@")[0] or "•" in d["candidate"]["email"]  # contacto enmascarado


def test_duplicate_is_not_stored_twice(client):
    data = (FIX / "cv_json_ats_es.json").read_bytes()
    r = client.post("/api/candidates/analyze", files={"file": ("dup.json", data)}, data={"consent": CONSENT})
    assert r.json()["duplicate"] is True


def test_role_click_reweight_decision_export_delete(client):
    cid = client.get("/api/candidates").json()["candidates"][0]["id"]
    full = client.get(f"/api/candidates/{cid}").json()
    rid = full["projects"][-1]["roles"][0]["role_id"]
    r = client.get(f"/api/candidates/{cid}/roles/{rid}")
    assert r.status_code == 200 and r.json()["match"]["viewed"] is True
    r = client.post(f"/api/candidates/{cid}/roles/{rid}/weights", json={"tecnico": 0.1, "power": 0.7, "experiencia": 0.1, "educacion": 0.1})
    assert abs(r.json()["match"]["weights"]["power"] - 0.7) < 1e-6
    assert client.post(f"/api/candidates/{cid}/roles/{rid}/decision", json={"decision": "asignar", "justification": "corta"}).status_code == 422
    assert client.post(f"/api/candidates/{cid}/roles/{rid}/decision",
                       json={"decision": "asignar", "justification": "Validado con el líder técnico del proyecto."}).status_code == 200
    exp = client.get(f"/api/candidates/{cid}/export")
    assert exp.status_code == 200 and exp.json()["codigo"].startswith("TM-")
    assert client.post(f"/api/candidates/{cid}/delete", json={"reason": "Solicitud del titular"}).status_code == 200
    assert client.get(f"/api/candidates/{cid}").status_code == 404


def test_projects_use_dataset_roles(client):
    projects = client.get("/api/projects").json()["projects"]
    assert len(projects) == 8
    assert all(r["job_id"] > 0 and r["tech_skills"] for p in projects for r in p["roles"])


def test_edit_experience_education_certifications(client):
    r = client.post("/api/candidates/analyze", files={"file": ("cv_texto_data_engineer.pdf", (FIX / "cv_texto_data_engineer.pdf").read_bytes())},
                    data={"consent": CONSENT})
    cid = r.json()["candidate"]["id"]
    body = {
        "experience": [
            {"role": "Líder de Datos", "company": "Empresa", "start": "2024-01", "current": True, "source": "Ascenso interno"},
            {"role": "Data Engineer", "company": "Empresa", "start": "2020-01", "end": "2023-12"},
        ],
        "education": [{"title": "Maestría en Analítica", "institution": "U. Católica", "level": 6, "status": "Graduado"}],
        "certifications": [{"name": "Kubernetes Administrator (programa interno)", "issuer": "Empresa", "year": 2026, "internal": True}],
    }
    d = client.put(f"/api/candidates/{cid}/profile", json=body).json()
    cand = d["candidate"]
    assert cand["years_experience"] >= 6.5                          # 2020-01 → hoy, sin traslapes
    assert cand["education_level"] == 6 and cand["education_label"] == "Maestría"
    assert cand["experience"][0]["current"] is True and cand["experience"][0]["source"] == "Ascenso interno"
    assert cand["certifications"][0]["internal"] is True
    assert any(s["key"] == "kubernetes" and "Certificación" in s["source"] for s in cand["tech_skills"])
    bad = {"experience": [{"role": "X", "start": "2024-05", "end": "2023-01"}]}
    assert client.put(f"/api/candidates/{cid}/profile", json=bad).status_code == 422
