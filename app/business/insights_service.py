"""Indicadores agregados de los datasets para la página de inicio (se calculan una sola vez)."""
from __future__ import annotations

from collections import Counter
from functools import lru_cache

from app.business.skill_catalog import all_job_requirements
from app.persistence.datasets import dataset_stats


@lru_cache(maxsize=1)
def dataset_insights() -> dict:
    reqs = all_job_requirements()
    tech, soft = Counter(), Counter()
    for r in reqs:
        tech.update(t["name"] for t in r["tech_skills"] if t["weight"] >= 1.0)
        soft.update(s["name"] for s in r["soft_skills"] if s["weight"] >= 1.0)
    from app.business.training_service import _index

    rated = _index()[0]   # cursos con calificación > 4.0
    bins = ["4.1–4.3", "4.4–4.6", "4.7–5.0"]

    def bucket(x):
        return bins[0] if x < 4.35 else (bins[1] if x < 4.65 else bins[2])

    dist = {p: Counter(rated[rated["platform"] == p]["rating"].map(bucket)) for p in ["Coursera", "Udemy"]}
    return {
        "stats": dataset_stats(),
        "top_tech": tech.most_common(12),
        "top_soft": soft.most_common(8),
        "rating_bins": bins,
        "rating_dist": {p: [dist[p].get(b, 0) for b in bins] for p in dist},
    }
