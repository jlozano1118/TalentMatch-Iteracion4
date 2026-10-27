"""Generación del plan de capacitación con Coursera.csv y Udemy_Courses.xlsx.

Sólo se recomiendan cursos con calificación ESTRICTAMENTE mayor a 4.0.
La relevancia se calcula con TF-IDF (título + habilidades del curso) y se combina con
la calificación. Cada brecha recibe hasta un curso por plataforma.
"""
from __future__ import annotations

import re
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.business.skill_catalog import SOFT_CANON, soft_query
from app.business.text_utils import fix_mojibake, norm
from app.config import MIN_COURSE_RATING
from app.persistence.datasets import load_courses

LEVEL_HOURS = {"beginner": 14, "intermediate": 22, "advanced": 30, "mixed": 18, "conversant": 16}
LEVEL_ES = {"beginner": "Principiante", "intermediate": "Intermedio", "advanced": "Avanzado", "mixed": "Mixto",
            "all levels": "Todos los niveles", "expert": "Experto", "conversant": "Intermedio"}
HOURS_PER_WEEK = 6


@lru_cache(maxsize=1)
def _index():
    df = load_courses()
    df = df[df["rating"].notna() & (df["rating"] > MIN_COURSE_RATING)].reset_index(drop=True)
    title = df["title"].map(norm)
    skills = df["skills"].map(lambda s: norm(fix_mojibake(s)))
    desc = df["description"].map(lambda s: norm(fix_mojibake(s))[:300])
    corpus = (title + " ") * 3 + (skills + " ") * 2 + desc
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, stop_words="english")
    mat = vec.fit_transform(corpus)
    df = df.drop(columns=["description"])   # ya no se necesita: ahorra memoria
    return df, vec, mat, title.tolist()


QUERY_EXPANSION = {
    "r": "r programming", "c": "c programming language", "go": "go golang programming", "aws": "aws amazon web services",
    "sql": "sql databases queries", "git": "git github version control", "ci/cd": "ci cd continuous integration devops",
    ".net": "net c# asp", "c#": "c# programming", "c++": "c++ programming", "etl": "etl data pipelines",
    "rest api": "rest api", "html": "html web", "css": "css web", "nosql": "nosql mongodb",
}
WEAK_TOKENS = {"iii", "ii", "skills", "skill", "management", "data", "analysis", "development", "programming",
               "and", "the", "for", "with", "web", "language", "tools", "systems", "system"}


def _query_for(skill: dict) -> str:
    if skill.get("type") == "power":
        return soft_query(skill["key"]) if skill["key"] in SOFT_CANON else skill["name"]
    return QUERY_EXPANSION.get(skill["key"], skill["key"])


def courses_for_skill(skill: dict, exclude: set[str], per_platform: int = 1) -> list[dict]:
    df, vec, mat, titles = _index()
    if skill.get("type") == "power" and skill["key"] not in SOFT_CANON:
        return []  # power skill no canónica: se reporta la brecha sin forzar un curso poco pertinente
    q = _query_for(skill)
    qv = vec.transform([norm(q)])
    if qv.nnz == 0:
        return []
    sims = (mat @ qv.T).toarray().ravel()
    q_tokens = [t for t in re.findall(r"[a-z0-9\+#\.]+", norm(skill.get("key", q))) if len(t) > 1 or t in {"r", "c"}]
    strong = [t for t in re.findall(r"[a-z0-9\+#\.]+", norm(q)) if (len(t) >= 3 or t in {"c#", "r", "go"}) and t not in WEAK_TOKENS]
    # Bonus si el término aparece literalmente en el título
    bonus = np.array([0.15 if q_tokens and all(re.search(rf"(?<![a-z]){re.escape(t)}(?![a-z])", ti) for t in q_tokens) else 0.0
                      for ti in titles]) if len(q_tokens) <= 3 else 0.0
    rating_norm = (df["rating"].to_numpy() - 4.0) / 1.0
    score = sims + bonus + 0.08 * rating_norm
    order = np.argsort(-score)
    picked: list[dict] = []
    per = {"Coursera": 0, "Udemy": 0}
    for i in order[:200]:
        if sims[i] < 0.12:
            break
        row = df.iloc[i]
        def _has(text: str) -> bool:
            return any(re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", text) for t in strong)

        if strong and not (_has(titles[i]) or (sims[i] >= 0.35 and _has(norm(row["skills"])))):
            continue
        if not strong and sims[i] < 0.3:
            continue
        if row["url"] in exclude or per[row["platform"]] >= per_platform:
            continue
        lvl_raw = str(row["level"]).strip().lower()
        hours = row["hours"]
        estimated = False
        if hours is None or (isinstance(hours, float) and np.isnan(hours)):
            hours = LEVEL_HOURS.get(lvl_raw, 18)
            estimated = True
        picked.append({
            "platform": row["platform"], "course_title": fix_mojibake(row["title"])[:300],
            "provider": fix_mojibake(row["provider"])[:200], "rating": float(row["rating"]),
            "level": LEVEL_ES.get(lvl_raw, str(row["level"]).title()), "hours": round(float(hours), 1),
            "hours_estimated": estimated, "url": row["url"], "relevance": round(float(sims[i]), 3),
        })
        per[row["platform"]] += 1
        exclude.add(row["url"])
        if all(v >= per_platform for v in per.values()):
            break
    return picked


def build_plan(match: dict, max_tech: int = 6, max_soft: int = 3) -> dict:
    """match: resultado de score_role. Devuelve brechas priorizadas con cursos."""
    gaps = []
    tech_gaps = sorted(match["missing_tech"], key=lambda x: (-x["weight"], x["credit"])) + \
        sorted(match["partial_tech"], key=lambda x: (-x["weight"], x["credit"]))
    for g in tech_gaps[:max_tech]:
        gaps.append({**g, "type": "tecnica"})
    for g in sorted(match["missing_soft"], key=lambda x: -x["weight"])[:max_soft]:
        gaps.append({**g, "type": "power"})

    exclude: set[str] = set()
    items, priority = [], 1
    for g in gaps:
        courses = courses_for_skill(g, exclude)
        for c in courses:
            items.append({"skill": g["name"], "skill_type": g["type"], "priority": priority, **c})
        if courses:
            priority += 1
    total_hours = round(sum(i["hours"] for i in items), 1)
    # Proyección: cerrar brechas técnicas/power cubiertas por el plan
    w = match["weights"]
    covered_t = {i["skill"] for i in items if i["skill_type"] == "tecnica"}
    covered_s = {i["skill"] for i in items if i["skill_type"] == "power"}
    reqs_t = match["matched_tech"] + match["partial_tech"] + match["missing_tech"]
    reqs_s = match["matched_soft"] + match["missing_soft"]

    def projected(reqs, covered):
        if not reqs:
            return 1.0
        tw = sum(r["weight"] for r in reqs)
        return sum(r["weight"] * (1.0 if r["name"] in covered else r["credit"]) for r in reqs) / tw

    proj = (w["tecnico"] * projected(reqs_t, covered_t) + w["power"] * projected(reqs_s, covered_s)
            + w["experiencia"] * match["exp_score"] / 100 + w["educacion"] * match["edu_score"] / 100) * 100
    return {
        "items": items,
        "gaps_without_course": [g["name"] for g in gaps if g["name"] not in {i["skill"] for i in items}],
        "total_hours": total_hours,
        "weeks": max(1, int(np.ceil(total_hours / HOURS_PER_WEEK))) if items else 0,
        "hours_per_week": HOURS_PER_WEEK,
        "projected_score": round(min(100.0, max(proj, match["score"])), 1),
    }
