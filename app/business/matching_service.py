"""Motor de matching explicable CV ↔ cargo.

Puntaje = w_tec·técnico + w_pow·power skills + w_exp·experiencia + w_edu·educación
Los pesos son dinámicos por naturaleza del cargo (recomendación del experto de RR. HH.)
y RR. HH. puede ajustarlos. Sólo se usan variables relacionadas con el trabajo:
nunca nombre, edad, género, foto, estado civil u origen (equidad / no discriminación).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.business.skill_catalog import EDU_LEVELS

TECH_HEAVY = {"Deep Learning", "Machine Learning", "Data Engineer", "Big Data Engineer", "Data Architect",
              "Full Stack Developer", "Cloud Services Developer", "Database Administrator", "Network Architect",
              "IT Systems Administrator", "Information Security Analyst", "Cloud Architect", "Data Warehousing",
              "Artificial Intelligence", "Statistics", "Data Scientist"}
POWER_HEAVY = {"Business Analyst", "IT Consultant", "Data and Analytics Manager"}
LEAD_WORDS = re.compile(r"\b(manager|lead|director|head|vp|vice president|principal|chief|gerente|jefe)\b", re.I)

# Habilidades relacionadas: dominar una da crédito parcial en la otra
RELATED = {
    "sql": {"mysql", "postgresql", "sql server", "oracle", "databases"},
    "databases": {"mysql", "postgresql", "sql server", "oracle", "mongodb", "sql", "nosql", "database management"},
    "nosql": {"mongodb", "cassandra", "redis", "elasticsearch"},
    "cloud computing": {"aws", "microsoft azure", "google cloud platform"},
    "aws": {"cloud computing", "microsoft azure", "google cloud platform"},
    "microsoft azure": {"aws", "google cloud platform", "cloud computing"},
    "google cloud platform": {"aws", "microsoft azure", "cloud computing"},
    "machine learning": {"deep learning", "scikit-learn", "tensorflow", "pytorch", "data science", "artificial intelligence"},
    "deep learning": {"tensorflow", "pytorch", "keras", "neural networks", "machine learning"},
    "artificial intelligence": {"machine learning", "deep learning", "natural language processing"},
    "data science": {"machine learning", "data analysis", "statistics", "python", "r"},
    "data analysis": {"data science", "statistics", "excel", "data visualization", "sql"},
    "data visualization": {"tableau", "power bi", "data analysis"},
    "business intelligence": {"power bi", "tableau", "data warehousing", "data visualization"},
    "big data": {"apache spark", "hadoop", "apache kafka", "hive"},
    "apache spark": {"big data", "hadoop", "scala"},
    "hadoop": {"big data", "apache spark", "hive"},
    "full stack development": {"front-end development", "back-end development", "web development", "javascript"},
    "back-end development": {"node.js", "java", "python", "spring boot", "django", "fastapi", "rest api"},
    "front-end development": {"react", "angular", "vue.js", "javascript", "html", "css"},
    "web development": {"html", "css", "javascript", "react", "angular"},
    "javascript": {"typescript", "react", "angular", "node.js", "vue.js"},
    "react": {"javascript", "react native"},
    "angular": {"typescript", "javascript"},
    "software development": {"java", "python", "c#", "javascript", "object-oriented programming"},
    "statistics": {"statistical analysis", "r", "data analysis"},
    "statistical analysis": {"statistics", "r", "sas"},
    "etl": {"data pipelines", "data warehousing", "apache airflow", "data engineering"},
    "data pipelines": {"etl", "apache airflow", "apache kafka", "data engineering"},
    "data engineering": {"etl", "data pipelines", "apache spark", "sql"},
    "information security": {"firewalls", "networking", "security compliance"},
    "networking": {"tcp/ip", "firewalls", "cisco"},
    "system administration": {"linux", "windows server", "active directory"},
    "devops": {"ci/cd", "docker", "kubernetes", "jenkins"},
    "ci/cd": {"devops", "jenkins", "git"},
    "agile": {"scrum"},
    "scrum": {"agile"},
    "project management": {"agile", "scrum"},
}

CAT_ES = {
    "Artificial Intelligence": "Inteligencia Artificial", "Big Data Engineer": "Ingeniería Big Data",
    "Business Analyst": "Análisis de Negocio", "Business Intelligence Analyst": "Inteligencia de Negocio",
    "Cloud Architect": "Arquitectura Cloud", "Cloud Services Developer": "Desarrollo Cloud",
    "Data Analyst": "Análisis de Datos", "Data Architect": "Arquitectura de Datos", "Data Engineer": "Ingeniería de Datos",
    "Data Quality Manager": "Calidad de Datos", "Data Scientist": "Ciencia de Datos",
    "Data Visualization Expert": "Visualización de Datos", "Data Warehousing": "Bodegas de Datos",
    "Data and Analytics Manager": "Gerencia de Datos y Analítica", "Database Administrator": "Administración de BD",
    "Deep Learning": "Deep Learning", "Full Stack Developer": "Desarrollo Full Stack", "IT Consultant": "Consultoría TI",
    "IT Systems Administrator": "Administración de Sistemas", "Information Security Analyst": "Seguridad de la Información",
    "Machine Learning": "Machine Learning", "Network Architect": "Arquitectura de Redes", "Statistics": "Estadística",
    "Technical Operations": "Operaciones Técnicas", "Technology Integration": "Integración Tecnológica",
}


def default_weights(category: str, title: str = "") -> dict:
    if category in POWER_HEAVY:
        w = {"tecnico": 0.35, "power": 0.40, "experiencia": 0.17, "educacion": 0.08}
        nature = "Rol orientado a personas y negocio"
    elif category in TECH_HEAVY:
        w = {"tecnico": 0.55, "power": 0.20, "experiencia": 0.17, "educacion": 0.08}
        nature = "Rol de alta especialización técnica"
    else:
        w = {"tecnico": 0.45, "power": 0.30, "experiencia": 0.17, "educacion": 0.08}
        nature = "Rol híbrido técnico-analítico"
    if LEAD_WORDS.search(title or ""):
        w["tecnico"] = round(w["tecnico"] - 0.10, 2)
        w["power"] = round(w["power"] + 0.10, 2)
        nature += " con responsabilidad de liderazgo"
    w["naturaleza"] = nature
    return w


def normalize_weights(w: dict) -> dict:
    keys = ["tecnico", "power", "experiencia", "educacion"]
    vals = {k: max(0.0, float(w.get(k, 0) or 0)) for k in keys}
    total = sum(vals.values()) or 1.0
    out = {k: round(v / total, 4) for k, v in vals.items()}
    if "naturaleza" in w:
        out["naturaleza"] = w["naturaleza"]
    return out


@dataclass
class CandidateSkills:
    tech: dict[str, str] = field(default_factory=dict)     # key → nombre visible
    soft: dict[str, str] = field(default_factory=dict)
    years: float = 0.0
    edu_level: int = 0

    @classmethod
    def from_profile(cls, tech_skills: list, soft_skills: list, years: float, edu_level: int) -> "CandidateSkills":
        return cls(
            tech={s["key"]: s["name"] for s in tech_skills},
            soft={s["key"]: s["name"] for s in soft_skills},
            years=float(years or 0), edu_level=int(edu_level or 0),
        )


def _phrase_in(small: str, big: str) -> bool:
    if len(small) < 3 and small not in {"r", "c", "go"}:
        return False
    return re.search(r"(^|[\s/(,-])" + re.escape(small) + r"($|[\s/),-])", big) is not None


def _credit(req_key: str, cv_keys: dict[str, str]) -> tuple[float, str | None]:
    """Crédito [0,1] para un requisito y la habilidad del CV que lo respalda."""
    if req_key in cv_keys:
        return 1.0, cv_keys[req_key]
    best, who = 0.0, None
    for k, name in cv_keys.items():
        c = 0.0
        if len(k) >= 3 and len(req_key) >= 3:
            ratio = fuzz.token_set_ratio(k, req_key)
            if ratio >= 92:
                c = 0.85
            elif _phrase_in(k, req_key) or _phrase_in(req_key, k):
                c = 0.7
        if c < 0.6 and (k in RELATED.get(req_key, ()) or req_key in RELATED.get(k, ())):
            c = 0.6
        if c > best:
            best, who = c, name
    return best, who


def _score_list(reqs: list[dict], cv_keys: dict[str, str]) -> tuple[float, list, list, list]:
    if not reqs:
        return 1.0, [], [], []
    total_w = sum(r["weight"] for r in reqs) or 1.0
    got = 0.0
    matched, partial, missing = [], [], []
    for r in reqs:
        credit, by = _credit(r["key"], cv_keys)
        got += credit * r["weight"]
        item = {"name": r["name"], "key": r["key"], "weight": r["weight"], "credit": round(credit, 2), "by": by}
        if credit >= 0.99:
            matched.append(item)
        elif credit >= 0.6:
            partial.append(item)
        else:
            missing.append(item)
    return got / total_w, matched, partial, missing


def experience_score(cv_years: float, req_years: float) -> float:
    req = req_years if req_years > 0 else 1.0
    return max(0.0, min(1.0, cv_years / req))


def education_score(cv_level: int, req_level: int) -> float:
    if req_level <= 0:
        return 1.0
    if cv_level <= 0:
        return 0.4
    if cv_level >= req_level:
        return 1.0
    if cv_level == req_level - 1:
        return 0.7
    return 0.35


def score_role(cand: CandidateSkills, role: dict, weights: dict | None = None) -> dict:
    w = normalize_weights(weights or role.get("weights") or default_weights(role["category"], role["title"]))
    tech_s, t_ok, t_part, t_miss = _score_list(role["tech_skills"], cand.tech)
    soft_s, s_ok, s_part, s_miss = _score_list(role["soft_skills"], cand.soft)
    exp_s = experience_score(cand.years, role.get("min_years", 0))
    edu_s = education_score(cand.edu_level, role.get("education_level", 0))
    total = w["tecnico"] * tech_s + w["power"] * soft_s + w["experiencia"] * exp_s + w["educacion"] * edu_s
    req_years = role.get("min_years", 0) or 0

    explanation = [
        f"Cubre {len(t_ok)} de {len(role['tech_skills'])} habilidades técnicas"
        + (f" y {len(t_part)} de forma parcial por habilidades relacionadas." if t_part else "."),
        f"Evidencia {len(s_ok) + len(s_part)} de {len(role['soft_skills'])} power skills requeridas.",
    ]
    if req_years:
        gap = req_years - cand.years
        if gap <= 0:
            explanation.append(f"Cumple la experiencia solicitada ({req_years:g} años; acredita {cand.years:g}).")
        elif gap <= 1:
            explanation.append(f"Está a {gap:.1f} años de la experiencia solicitada ({req_years:g} años): muy cerca de cumplir.")
        else:
            explanation.append(f"Le faltan {gap:.1f} años para la experiencia solicitada ({req_years:g} años).")
    else:
        explanation.append("La oferta no exige años específicos; se toma 1 año como referencia.")
    if role.get("education_level", 0):
        explanation.append(
            f"Formación requerida: {EDU_LEVELS[role['education_level']]}; acreditada: {EDU_LEVELS.get(cand.edu_level, 'No identificada')}.")
    top_missing = sorted(t_miss, key=lambda x: -x["weight"])[:3]
    if top_missing:
        explanation.append("Brechas prioritarias: " + ", ".join(m["name"] for m in top_missing) + ".")

    return {
        "score": round(total * 100, 1),
        "tech_score": round(tech_s * 100, 1),
        "soft_score": round(soft_s * 100, 1),
        "exp_score": round(exp_s * 100, 1),
        "edu_score": round(edu_s * 100, 1),
        "weights": w,
        "matched_tech": t_ok, "partial_tech": t_part, "missing_tech": t_miss,
        "matched_soft": s_ok + s_part, "missing_soft": s_miss,
        "explanation": explanation,
    }


def quick_market_score(cand: CandidateSkills, req: dict) -> tuple[float, list]:
    """Puntaje rápido (coincidencia exacta + relacionadas) para recorrer las 3.000 ofertas."""
    tech = req["tech_skills"]
    if len(tech) < 4:
        return 0.0, []
    tw = sum(t["weight"] for t in tech)
    got, matched = 0.0, []
    for t in tech:
        if t["key"] in cand.tech:
            got += t["weight"]
            matched.append(t["name"])
        elif any(k in RELATED.get(t["key"], ()) for k in cand.tech):
            got += 0.6 * t["weight"]
    soft = req["soft_skills"]
    s = (sum(1 for x in soft if x["key"] in cand.soft) / len(soft)) if soft else 0.5
    return round((0.75 * got / tw + 0.25 * s) * 100, 1), matched
