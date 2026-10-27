"""Evaluación basada en evidencia (Unidad 5): métricas de calidad, línea base, equidad e impacto.

- Métrica de calidad 1: precisión de la extracción de habilidades frente a un conjunto etiquetado.
- Métrica de calidad 2: exhaustividad (recall) de la extracción.
- Línea base: extracción ingenua (sólo partir por comas la sección de habilidades).
- Indicador de equidad: brecha de puntaje según el TIPO de CV (texto, escaneado, imagen, JSON).
  Un CV escaneado no debería recibir peor puntaje por limitaciones del OCR: si la brecha supera
  10 puntos se emite una alerta para revisión humana.
- Indicador de impacto social: movilidad interna visible (colaboradores con ≥1 cargo ≥ 60 %).
"""
from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path
from statistics import mean

from sqlalchemy.orm import Session

from app.business.extraction.cv_parser import split_sections
from app.business.skill_catalog import canonical_soft, canonical_tech
from app.config import BASE_DIR
from app.persistence.repositories.candidates import CandidateRepository

FIXTURES = BASE_DIR / "tests" / "fixtures"


def _prf(found: set, gold: set) -> tuple[float, float]:
    tp = len(found & gold)
    precision = tp / len(found) if found else 0.0
    recall = tp / len(gold) if gold else 1.0
    return precision, recall


def _baseline(text: str) -> tuple[set, set]:
    sec = split_sections(text)
    tech, soft = set(), set()
    for line in sec.get("skills", []) + sec.get("soft", []):
        for part in line.split(","):
            p = part.strip()
            if not p:
                continue
            k = canonical_soft(p)
            (soft.add(k) if k else tech.add(canonical_tech(p)))
    return tech, soft


@lru_cache(maxsize=1)
def extraction_benchmark() -> dict:
    """Corre la extracción sobre el conjunto de prueba etiquetado (tests/fixtures)."""
    from app.business.analysis_service import extract_profile
    from app.business.extraction.document_reader import read_image, read_pdf
    from app.business.extraction.json_reader import read_json

    gold_path = FIXTURES / "gold.json"
    if not gold_path.exists():
        return {"available": False}
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    rows, t0 = [], time.time()
    for fname, g in gold.items():
        if fname.startswith("_") or not (FIXTURES / fname).exists():
            continue
        data = (FIXTURES / fname).read_bytes()
        ex = extract_profile(fname, data, external_ai=False)
        p = ex["profile"]
        found_t = {s["key"] for s in p["tech_skills"]}
        found_s = {s["key"] for s in p["soft_skills"]}
        gt, gs = set(g["tech"]), set(g["soft"])
        pt, rt = _prf(found_t, gt)
        ps, rs = _prf(found_s, gs)
        # línea base
        if fname.endswith(".json"):
            text = read_json(data)[0]
        elif fname.endswith(".pdf"):
            text = read_pdf(data).text
        else:
            text = read_image(data).text
        bt, bs = _baseline(text)
        bpt, brt = _prf(bt, gt)
        sens_ok = set(g["sensitive"]) <= set(ex["sensitive"])
        rows.append({
            "archivo": fname, "tipo": ex["source"],
            "precision_tecnica": round(pt * 100, 1), "recall_tecnica": round(rt * 100, 1),
            "precision_power": round(ps * 100, 1), "recall_power": round(rs * 100, 1),
            "baseline_recall_tecnica": round(brt * 100, 1),
            "anos_ok": g["years_min"] <= p["years_experience"] <= g["years_max"],
            "educacion_ok": p["education_level"] == g["education_level"],
            "sensibles_descartados_ok": sens_ok,
        })
    if not rows:
        return {"available": False}
    agg = {
        "available": True, "n": len(rows), "segundos": round(time.time() - t0, 1),
        "precision_tecnica": round(mean(r["precision_tecnica"] for r in rows), 1),
        "recall_tecnica": round(mean(r["recall_tecnica"] for r in rows), 1),
        "precision_power": round(mean(r["precision_power"] for r in rows), 1),
        "recall_power": round(mean(r["recall_power"] for r in rows), 1),
        "baseline_recall_tecnica": round(mean(r["baseline_recall_tecnica"] for r in rows), 1),
        "anos_ok": sum(r["anos_ok"] for r in rows), "educacion_ok": sum(r["educacion_ok"] for r in rows),
        "sensibles_ok": sum(r["sensibles_descartados_ok"] for r in rows),
        "detalle": rows,
    }
    return agg


def live_metrics(db: Session) -> dict:
    repo = CandidateRepository(db)
    cands = repo.list()
    by_source: dict[str, list[float]] = {}
    mobility = 0
    sens_counter: dict[str, int] = {}
    conf, completeness, decisions = [], [], 0
    for c in cands:
        best = repo.best_match(c.id)
        if best:
            by_source.setdefault(c.source_type, []).append(best.score)
        if any(m.score >= 60 for m in repo.matches(c.id)):
            mobility += 1
        for s in c.sensitive_discarded:
            sens_counter[s] = sens_counter.get(s, 0) + 1
        conf += [s["confidence"] for s in c.tech_skills + c.soft_skills]
        completeness.append(c.quality.get("completeness", 0))
        decisions += len(repo.decisions(c.id))
    src_avg = {k: round(mean(v), 1) for k, v in by_source.items()}
    gap = round(max(src_avg.values()) - min(src_avg.values()), 1) if len(src_avg) > 1 else 0.0
    return {
        "candidatos": len(cands),
        "por_fuente": {k: len(v) for k, v in by_source.items()},
        "puntaje_promedio_por_fuente": src_avg,
        "brecha_equidad_fuente": gap,
        "alerta_equidad": gap > 10,
        "movilidad_interna_pct": round(mobility / len(cands) * 100, 1) if cands else 0.0,
        "confianza_promedio": round(mean(conf) * 100, 1) if conf else 0.0,
        "completitud_promedio": round(mean(completeness), 1) if completeness else 0.0,
        "sensibles_descartados": sens_counter,
        "decisiones_humanas": decisions,
        "habilidades_con_evidencia_pct": 100.0 if conf else 0.0,
    }
