"""Catálogo de habilidades construido a partir de JobsDatasetProcessed.csv.

- Normaliza y canoniza habilidades técnicas y power skills (ES ↔ EN).
- Convierte cada oferta del dataset en requisitos estructurados.
- Expone el vocabulario usado para extraer habilidades de los CV.
"""
from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache

from app.business.text_utils import clean_display, norm
from app.persistence.datasets import load_jobs

# ---------------------------------------------------------------------------
# Power skills canónicas (habilidades transversales). Etiqueta en español para la UI
# y término en inglés para buscar cursos en Coursera/Udemy.
# ---------------------------------------------------------------------------
SOFT_CANON: dict[str, dict] = {
    "communication": {"label": "Comunicación", "query": "communication skills", "syn": [
        "communication", "communication skills", "verbal communication", "written communication",
        "verbal and written communication", "communicator", "comunicacion", "comunicacion asertiva",
        "comunicacion efectiva", "comunicacion oral y escrita", "strong communication skills",
        "excellent communication skills", "communication/presentation skills"]},
    "teamwork": {"label": "Trabajo en equipo", "query": "high performance collaboration teamwork leadership", "syn": [
        "teamwork", "team player", "collaboration", "collaborative", "team collaboration", "cooperation",
        "trabajo en equipo", "colaboracion", "trabajo colaborativo", "cross-functional collaboration", "team-oriented", "team oriented"]},
    "problem_solving": {"label": "Resolución de problemas", "query": "problem solving", "syn": [
        "problem-solving", "problem solving", "problem-solving skills", "problem solver", "resolucion de problemas",
        "solucion de problemas", "analytical problem-solving", "problem resolution", "solving problems"]},
    "leadership": {"label": "Liderazgo", "query": "leadership", "syn": [
        "leadership", "team leadership", "liderazgo", "lider de equipo", "people management", "team management",
        "visionary leadership", "leadership skills", "gestion de equipos", "lideres"]},
    "critical_thinking": {"label": "Pensamiento crítico", "query": "critical thinking", "syn": [
        "critical thinking", "pensamiento critico", "analytical thinking", "analytical skills", "pensamiento analitico",
        "analytical mindset", "capacidad de analisis", "analytical", "logical thinking", "analysis", "research skills"]},
    "adaptability": {"label": "Adaptabilidad", "query": "adaptability resilience", "syn": [
        "adaptability", "flexibility", "adaptabilidad", "flexibilidad", "resilience", "resiliencia", "resilient",
        "adaptable", "agile learner"]},
    "attention_to_detail": {"label": "Atención al detalle", "query": "attention to detail quality", "syn": [
        "attention to detail", "detail-oriented", "detail oriented", "atencion al detalle", "meticuloso", "precision"]},
    "time_management": {"label": "Gestión del tiempo", "query": "time management productivity", "syn": [
        "time management", "gestion del tiempo", "prioritization", "priorizacion", "multi-tasking", "multitasking",
        "manejo del tiempo", "ability to prioritize"]},
    "organization": {"label": "Organización y planificación", "query": "organizational skills planning", "syn": [
        "organizational skills", "organization", "organizacion", "planificacion", "planning", "organized",
        "planning and organization"]},
    "creativity": {"label": "Creatividad e innovación", "query": "creativity innovation", "syn": [
        "creativity", "innovation", "creatividad", "innovacion", "creative", "innovative", "creative thinking",
        "pensamiento creativo"]},
    "empathy": {"label": "Empatía e inteligencia emocional", "query": "emotional intelligence empathy", "syn": [
        "empathy", "empatia", "emotional intelligence", "inteligencia emocional", "active listening",
        "escucha activa"]},
    "interpersonal": {"label": "Relaciones interpersonales", "query": "interpersonal skills relationship building", "syn": [
        "interpersonal skills", "relationship building", "relaciones interpersonales", "stakeholder management",
        "relationship management", "networking skills", "interpersonal", "habilidades interpersonales", "building relationships", "effective relationships"]},
    "customer_orientation": {"label": "Orientación al cliente", "query": "customer service", "syn": [
        "customer service", "customer focus", "orientacion al cliente", "servicio al cliente", "customer-focused",
        "client focus", "customer relationship management", "customer engagement", "atencion al cliente"]},
    "decision_making": {"label": "Toma de decisiones", "query": "decision making", "syn": [
        "decision-making", "decision making", "toma de decisiones", "judgment", "sound judgment"]},
    "strategic_thinking": {"label": "Pensamiento estratégico", "query": "strategic thinking", "syn": [
        "strategic thinking", "pensamiento estrategico", "vision estrategica", "business acumen", "strategic mindset"]},
    "initiative": {"label": "Iniciativa y proactividad", "query": "personal effectiveness initiative", "syn": [
        "initiative", "self-motivation", "self-motivated", "proactive", "proactividad", "iniciativa", "self-starter",
        "motivated", "autonomia", "autonomous", "independent", "drive", "initiative-taking", "proactivo"]},
    "presentation": {"label": "Presentaciones y oratoria", "query": "public speaking presentation skills", "syn": [
        "presentation skills", "public speaking", "presentaciones", "hablar en publico", "oratoria", "presentation",
        "storytelling"]},
    "mentoring": {"label": "Mentoría y coaching", "query": "coaching mentoring", "syn": [
        "mentoring", "coaching", "mentoria", "team coaching", "training skills", "formacion de equipos"]},
    "negotiation": {"label": "Negociación e influencia", "query": "negotiation persuasion", "syn": [
        "negotiation", "negociacion", "persuasion", "influence", "influencing", "persuasive"]},
    "continuous_learning": {"label": "Aprendizaje continuo", "query": "learning how to learn", "syn": [
        "continuous learning", "aprendizaje continuo", "curiosity", "curiosidad", "eager to learn", "autodidacta",
        "willingness to learn", "learning agility", "growth mindset", "quick learner", "fast learner", "aprendizaje rapido"]},
    "accountability": {"label": "Responsabilidad y ética", "query": "business ethics professionalism", "syn": [
        "accountability", "professionalism", "responsabilidad", "integrity", "integridad", "etica profesional",
        "compromiso", "commitment", "reliability", "dependable", "work ethic", "transparent"]},
    "conflict_resolution": {"label": "Resolución de conflictos", "query": "conflict resolution", "syn": [
        "conflict resolution", "resolucion de conflictos", "conflict management", "manejo de conflictos"]},
    "pressure": {"label": "Trabajo bajo presión", "query": "stress management resilience", "syn": [
        "work under pressure", "trabajo bajo presion", "stress management", "manejo del estres",
        "ability to work under pressure", "fast-paced", "high-paced", "fast-paced environment", "high-paced environment"]},
}

# Términos que evidencian una power skill dentro de logros del CV (inferencia con confianza menor)
SOFT_INFERENCE = {
    "leadership": [r"\blider(e|é)?\b", r"\bdirig[ií]", r"\bcoordin[eéa]", r"\bled a team\b", r"\bmanaged a team\b", r"\bequipo de \d+"],
    "teamwork": [r"\bequipos? multidisciplinarios?\b", r"\bcross-functional\b", r"\bcolabor[eéa]"],
    "communication": [r"\bexpuse\b", r"\bpresent[eé] resultados\b", r"\bstakeholders?\b", r"\bdocument[eé]\b"],
    "mentoring": [r"\bmentor[ié]?\b", r"\bcapacit[eé]\b", r"\bform[eé] a\b", r"\btrained\b"],
    "problem_solving": [r"\bresolv[ií]\b", r"\bsolucion[eé]\b", r"\boptimic[eé]\b", r"\breduje\b"],
    "customer_orientation": [r"\bclientes?\b"],
}

# ---------------------------------------------------------------------------
# Sinónimos técnicos (alias → canónico en inglés, que es el idioma del dataset)
# ---------------------------------------------------------------------------
TECH_SYNONYMS: dict[str, list[str]] = {
    "javascript": ["js", "javascript", "java script", "ecmascript", "es6"],
    "typescript": ["typescript", "ts"],
    "node.js": ["node", "nodejs", "node.js", "node.js (es6)", "node js"],
    "react": ["react", "reactjs", "react.js", "react js"],
    "react native": ["react native"],
    "vue.js": ["vue", "vuejs", "vue.js"],
    "angular": ["angular", "angularjs", "angular.js"],
    "postgresql": ["postgres", "postgresql", "postgre sql"],
    "mongodb": ["mongo", "mongodb", "mongo db"],
    "sql server": ["ms sql", "sql server", "microsoft sql server", "mssql", "microsoft sql", "t-sql"],
    "aws": ["aws", "amazon web services", "aws services", "amazon aws", "aws cloud"],
    "google cloud platform": ["gcp", "google cloud platform", "google cloud"],
    "microsoft azure": ["azure", "microsoft azure", "azure cloud"],
    "machine learning": ["ml", "machine learning", "aprendizaje automatico", "machine learning techniques"],
    "deep learning": ["deep learning", "aprendizaje profundo", "dl"],
    "artificial intelligence": ["ai", "artificial intelligence", "inteligencia artificial", "ia"],
    "natural language processing": ["nlp", "natural language processing", "procesamiento de lenguaje natural", "pln"],
    "computer vision": ["computer vision", "vision por computador", "vision artificial", "machine vision"],
    "neural networks": ["neural networks", "redes neuronales"],
    "excel": ["excel", "microsoft excel", "ms excel", "advanced excel", "excel avanzado"],
    "power bi": ["power bi", "powerbi", "microsoft power bi"],
    "c#": ["c#", "c sharp", "csharp"],
    ".net": [".net", "net", "dotnet", "asp.net", ".net core", "net development"],
    "go": ["golang", "go"],
    "kubernetes": ["kubernetes", "k8s"],
    "ci/cd": ["ci/cd", "continuous integration", "continuous deployment", "continuous delivery", "integracion continua",
              "despliegue continuo", "ci/cd pipelines"],
    "rest api": ["rest", "rest api", "restful", "http/rest", "rest apis", "restful apis", "api rest", "apis rest",
                 "web services", "api development", "desarrollo de apis"],
    "object-oriented programming": ["oop", "object-oriented programming", "programacion orientada a objetos", "poo",
                                    "object-oriented programming (oop)", "object oriented programming"],
    "databases": ["databases", "bases de datos", "base de datos", "relational databases", "database", "rdbms",
                  "bases de datos relacionales"],
    "nosql": ["nosql", "non-relational databases", "bases de datos no relacionales"],
    "database management": ["database management", "gestion de bases de datos", "administracion de bases de datos",
                            "database administration", "dba"],
    "database design": ["database design", "diseno de bases de datos"],
    "data analysis": ["data analysis", "analisis de datos", "data analytics", "analitica de datos"],
    "data visualization": ["data visualization", "visualizacion de datos", "dashboards", "tableros", "dashboard development"],
    "data mining": ["data mining", "mineria de datos"],
    "data modeling": ["data modeling", "modelado de datos", "modelamiento de datos", "data modelling"],
    "statistics": ["statistics", "estadistica"],
    "statistical analysis": ["statistical analysis", "analisis estadistico", "statistical modeling", "modelos estadisticos"],
    "project management": ["project management", "gestion de proyectos", "gerencia de proyectos", "administracion de proyectos"],
    "agile": ["agile", "agile methodology", "metodologias agiles", "agile development", "agile methodologies", "metodologia agil",
              "agile project management"],
    "scrum": ["scrum"],
    "cloud computing": ["cloud computing", "computacion en la nube", "cloud", "cloud services", "nube", "cloud infrastructure"],
    "networking": ["networking", "redes", "redes de computadores", "network administration", "redes de datos",
                   "telecomunicaciones", "network environments"],
    "information security": ["information security", "seguridad de la informacion", "ciberseguridad", "cybersecurity",
                             "seguridad informatica", "security", "network security", "data protection"],
    "web development": ["web development", "desarrollo web", "web application development", "web programming"],
    "software development": ["software development", "desarrollo de software", "software engineering", "ingenieria de software"],
    "full stack development": ["full stack development", "full stack", "desarrollo full stack", "full stack web development", "fullstack"],
    "front-end development": ["front-end development", "frontend", "front-end", "desarrollo frontend"],
    "back-end development": ["back-end development", "backend", "back-end", "desarrollo backend", "back-end programming"],
    "data warehousing": ["data warehousing", "data warehouse", "bodega de datos", "almacen de datos", "dwh"],
    "business intelligence": ["business intelligence", "inteligencia de negocios", "bi", "business intelligence tools"],
    "etl": ["etl", "etl processes", "etl development", "procesos etl", "elt/etl development", "etl/elt"],
    "big data": ["big data", "big data technologies", "big data platforms"],
    "linux": ["linux", "unix/linux", "linux/unix", "unix", "unix/linux systems"],
    "software testing": ["testing", "pruebas de software", "software testing", "qa", "quality assurance", "pruebas"],
    "unit testing": ["unit testing", "pruebas unitarias"],
    "microservices": ["microservices", "microservicios", "microservices architecture", "arquitectura de microservicios"],
    "data engineering": ["data engineering", "ingenieria de datos"],
    "data science": ["data science", "ciencia de datos"],
    "data pipelines": ["data pipelines", "pipelines de datos", "data processing pipelines"],
    "system administration": ["system administration", "systems administration", "administracion de sistemas",
                              "administracion de servidores", "sysadmin"],
    "requirements gathering": ["requirements gathering", "levantamiento de requerimientos", "levantamiento de requisitos",
                               "requirements analysis", "business requirements"],
    "business analysis": ["business analysis", "analisis de negocio", "analisis de negocios"],
    "process improvement": ["process improvement", "mejora de procesos", "business process improvement", "mejora continua"],
    "technical documentation": ["technical documentation", "documentacion tecnica", "documentation"],
    "shell scripting": ["shell scripting", "bash", "shell", "scripting", "shell scripting (bash)"],
    "html": ["html", "html5"],
    "css": ["css", "css3"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "apache spark": ["spark", "apache spark", "pyspark"],
    "apache kafka": ["kafka", "apache kafka"],
    "apache airflow": ["airflow", "apache airflow"],
    "hadoop": ["hadoop", "hdfs", "hadoop / mapreduce"],
    "oracle": ["oracle", "oracle databases", "oracle database", "pl/sql"],
    "amazon redshift": ["redshift", "amazon redshift"],
    "spring boot": ["spring", "spring boot", "spring framework"],
    "git": ["git", "github", "gitlab", "control de versiones", "version control", "source control"],
    "docker": ["docker", "docker container", "contenedores", "containers"],
    "troubleshooting": ["troubleshooting", "diagnostico de fallas", "soporte tecnico", "technical support"],
    "virtualization": ["virtualization", "virtualizacion", "vmware"],
    "tcp/ip": ["tcp/ip", "tcp ip"],
    "firewalls": ["firewalls", "firewall"],
    "devops": ["devops"],
    "mlops": ["mlops"],
    "uml": ["uml"],
    "jira": ["jira"],
    "figma": ["figma"],
    "tableau": ["tableau"],
    "python": ["python", "python 3", "python3"],
    "java": ["java", "java se", "java ee"],
    "software development life cycle": ["software development life cycle", "sdlc", "ciclo de vida del software"],
    "sql": ["sql", "sql queries", "sql development"],
    "mysql": ["mysql"],
    "php": ["php"],
    "c++": ["c++", "cpp"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "tensorflow": ["tensorflow"],
    "pytorch": ["pytorch"],
    "django": ["django"],
    "flask": ["flask"],
    "fastapi": ["fastapi"],
    "jenkins": ["jenkins"],
    "ansible": ["ansible"],
    "terraform": ["terraform"],
    "scala": ["scala"],
    "sas": ["sas"],
    "matlab": ["matlab"],
    "javafx": ["javafx"],
    "kotlin": ["kotlin"],
    "swift": ["swift"],
    "windows server": ["windows server", "windows"],
    "active directory": ["active directory"],
}

SHORT_AMBIGUOUS = {"r", "c", "go", "ts", "ia", "ai", "bi", "dl", "ml", "qa", "net", "poo", "pln", "dba", "js", "cloud",
                   "security", "testing", "pruebas", "redes", "nube", "shell", "scripting", "windows", "spring",
                   "documentation", "drive", "planning", "analytical", "organization", "presentation"}

_JUNK = re.compile(r"^(technical skills|soft skills|skills|it skills|none|n/a|not specified|other|etc)\b")
_PREFIX = re.compile(r"^(strong|excellent|advanced|basic|good|solid|proven|deep|working|demonstrated|proficiency in|"
                     r"proficient in|knowledge of|experience (with|in)|familiarity with|understanding of|expertise in|ability to)\s+")

EDU_LEVELS = {
    0: "No especificado", 1: "Bachiller", 2: "Técnico", 3: "Tecnólogo", 4: "Profesional (pregrado)",
    5: "Especialización", 6: "Maestría", 7: "Doctorado",
}

EDU_PATTERNS = [
    (7, r"\b(ph\.?\s?d|doctorate|doctoral|doctorado|doctor en)\b"),
    (6, r"\b(master'?s?|m\.s\.|mba|maestria|magister|msc|m\.sc)\b"),
    (5, r"\b(especializacion|especialista en|postgraduate|posgrado)\b"),
    (4, r"\b(bachelor'?s?|b\.s\.|b\.a\.|bs degree|ba degree|undergraduate|degree in|college degree|university degree|ingenier[oa]|ingenieria|"
        r"pregrado|profesional en|licenciad[oa]|computer science engineering degree|4-year degree|four-year degree)\b"),
    (3, r"\b(associate'?s? degree|tecnolog[oa]|tecnologia en)\b"),
    (2, r"\b(tecnico|technical certificate|vocational)\b"),
    (1, r"\b(high school|bachiller|ged|secondary school)\b"),
]


# ---------------------------------------------------------------------------
# Canonización
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _alias_index() -> tuple[dict[str, str], dict[str, str]]:
    tech, soft = {}, {}
    for canon, aliases in TECH_SYNONYMS.items():
        for a in aliases + [canon]:
            tech[norm(a)] = canon
    for key, info in SOFT_CANON.items():
        for a in info["syn"]:
            soft[norm(a)] = key
    return tech, soft


def _strip_noise(text: str) -> str:
    t = norm(text)
    t = t.lstrip("-–>+ ")
    t = _PREFIX.sub("", t)
    t = re.sub(r"\s+(skills?|abilities)$", "", t) if not t.endswith("problem-solving skills") else t
    return t.strip()


@lru_cache(maxsize=None)
def canonical_soft(text: str) -> str | None:
    _, soft = _alias_index()
    t = norm(text)
    if t in soft:
        return soft[t]
    t2 = _strip_noise(text)
    if t2 in soft:
        return soft[t2]
    for suffix in (" skills", " skill"):
        if (t2 + suffix) in soft:
            return soft[t2 + suffix]
    # Contención: "Judgment and decision making" → decision_making
    rx, lookup = _soft_contain_rx()
    m = rx.search(t2)
    if m:
        return lookup[m.group(1)]
    # Tolerancia a errores de OCR ("Gestién del tiempo")
    if 5 <= len(t2) <= 40:
        from rapidfuzz import fuzz, process

        best = process.extractOne(t2, list(soft.keys()), scorer=fuzz.ratio, score_cutoff=88)
        if best:
            return soft[best[0]]
    return None


@lru_cache(maxsize=1)
def _soft_contain_rx():
    items = _soft_contain_list()
    rx = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(a) for a, _ in items) + r")(?![a-z0-9])")
    return rx, dict(items)


@lru_cache(maxsize=1)
def _soft_contain_list() -> list[tuple[str, str]]:
    _, soft = _alias_index()
    items = [(a, k) for a, k in soft.items() if len(a) >= 6 and a not in {"analytical", "analysis", "planning", "organized",
             "creative", "presentation", "organization", "security", "influence", "drive", "precision"}]
    return sorted(items, key=lambda x: -len(x[0]))


@lru_cache(maxsize=None)
def canonical_tech(text: str) -> str:
    tech, _ = _alias_index()
    t = norm(text)
    if t in tech:
        return tech[t]
    t2 = _strip_noise(text)
    return tech.get(t2, t2)


def soft_label(key: str) -> str:
    info = SOFT_CANON.get(key)
    return info["label"] if info else clean_display(key).capitalize()


def soft_query(key: str) -> str:
    info = SOFT_CANON.get(key)
    return info["query"] if info else key


def split_skill_list(raw: str) -> list[str]:
    """Separa por comas respetando paréntesis y expande 'Programming (Python, C++)'."""
    if not raw:
        return []
    out: list[str] = []
    for part in re.split(r",(?![^()]*\))|;|\n", raw):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(.*?)\(([^)]*)\)\s*$", part)
        if m:
            head, inner = m.group(1).strip(), m.group(2)
            inner_items = [i.strip() for i in re.split(r"[,/]| or | and ", inner) if i.strip()]
            if head:
                out.append(head)
            if 0 < len(inner_items) <= 8:
                out.extend(inner_items)
        else:
            out.append(part)
    cleaned = []
    for item in out:
        t = norm(item)
        if not t or len(t) < 1 or _JUNK.match(t) or len(t.split()) > 7 or t.endswith(":"):
            continue
        cleaned.append(clean_display(item))
    return cleaned


def detect_education_level(text: str) -> list[int]:
    t = norm(text)
    found = [lvl for lvl, pat in EDU_PATTERNS if re.search(pat, t)]
    return found


def detect_min_years(text: str) -> float:
    t = norm(text)
    years = []
    for m in re.finditer(r"(\d{1,2})\s*\+?\s*(?:-|to|a)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs|anos|años)", t):
        v = int(m.group(1))
        if 1 <= v <= 15:
            years.append(v)
    return float(min(years)) if years else 0.0


# ---------------------------------------------------------------------------
# Vocabulario y requisitos del dataset
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def tech_frequency() -> Counter:
    jobs = load_jobs()
    c: Counter = Counter()
    for raw in jobs["IT Skills"]:
        keys = set()
        for s in split_skill_list(raw):
            if canonical_soft(s):
                continue
            keys.add(canonical_tech(s))
        c.update(keys)
    return c


@lru_cache(maxsize=1)
def tech_vocabulary() -> dict[str, str]:
    """alias normalizado → canónico. Incluye sinónimos curados + términos del dataset con frecuencia ≥ 3."""
    tech, _ = _alias_index()
    vocab = dict(tech)
    for key, freq in tech_frequency().items():
        if freq >= 3 and 2 <= len(key) <= 40 and len(key.split()) <= 4 and not key.isdigit():
            vocab.setdefault(key, key)
    return vocab


def display_tech(key: str) -> str:
    special = {"aws": "AWS", "sql": "SQL", "etl": "ETL", "nosql": "NoSQL", "html": "HTML", "css": "CSS", "php": "PHP",
               "sas": "SAS", "uml": "UML", "git": "Git", "c#": "C#", "c++": "C++", ".net": ".NET", "ci/cd": "CI/CD",
               "rest api": "REST API", "mysql": "MySQL", "postgresql": "PostgreSQL", "mongodb": "MongoDB",
               "node.js": "Node.js", "vue.js": "Vue.js", "tcp/ip": "TCP/IP", "devops": "DevOps", "mlops": "MLOps",
               "power bi": "Power BI", "javascript": "JavaScript", "typescript": "TypeScript", "fastapi": "FastAPI",
               "pytorch": "PyTorch", "tensorflow": "TensorFlow", "numpy": "NumPy", "javafx": "JavaFX",
               "scikit-learn": "scikit-learn", "jira": "Jira", "r": "R", "c": "C", "go": "Go", "matlab": "MATLAB",
               "sql server": "SQL Server", "amazon redshift": "Amazon Redshift", "hadoop": "Hadoop"}
    if key in special:
        return special[key]
    upper = {"api", "bi", "ai", "ml", "erp", "crm", "sap", "aws", "gcp", "ui", "ux", "qa", "it", "sql", "etl", "nlp", "ec2", "s3"}
    small = {"of", "and", "the", "in", "de", "for", "to", "y", "en"}
    words = []
    for w in key.split():
        words.append(w.upper() if w in upper else (w if w in small else w[:1].upper() + w[1:]))
    return " ".join(words)


def parse_job_requirements(row) -> dict:
    """Convierte una fila del dataset en requisitos estructurados para el matching."""
    freq = tech_frequency()
    tech, soft, seen_t, seen_s = [], [], set(), set()
    for s in split_skill_list(row["IT Skills"]):
        sk = canonical_soft(s)
        if sk:
            if sk not in seen_s:
                seen_s.add(sk)
                soft.append({"key": sk, "name": soft_label(sk), "weight": 1.0})
            continue
        key = canonical_tech(s)
        if key in seen_t or len(key) < 1:
            continue
        seen_t.add(key)
        weight = 1.0 if freq.get(key, 0) >= 5 else 0.6
        tech.append({"key": key, "name": display_tech(key) if key in tech_vocabulary() else clean_display(s), "weight": weight})
    for s in split_skill_list(row["Soft Skills"]):
        sk = canonical_soft(s)
        key = sk or norm(s)
        if key in seen_s or not key or key.startswith(("of ", "and ", "to ", "with ")) or len(key) < 4:
            continue
        seen_s.add(key)
        soft.append({"key": key, "name": soft_label(sk) if sk else clean_display(s).capitalize(), "weight": 1.0 if sk else 0.5})

    edu_text = " ".join([row["Education"], row["Description"]])
    levels = detect_education_level(edu_text)
    edu_level = min(levels) if levels else 0
    min_years = detect_min_years(" ".join([row["Experience"], row["Description"]]))
    desc = clean_display(row["Description"])
    return {
        "job_id": int(row["ID"]),
        "title": clean_display(row["Job Title"]).split(" - ")[0][:120] or row["Query"],
        "category": row["Query"],
        "tech_skills": tech[:18],
        "soft_skills": soft[:10],
        "min_years": min_years,
        "education_level": edu_level,
        "education_label": EDU_LEVELS[edu_level],
        "summary": (desc[:420] + "…") if len(desc) > 420 else desc,
    }


@lru_cache(maxsize=1)
def all_job_requirements() -> list[dict]:
    jobs = load_jobs()
    return [parse_job_requirements(r) for _, r in jobs.iterrows()]
