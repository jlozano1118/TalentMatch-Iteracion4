"""Parser determinista de hojas de vida (texto → perfil estructurado).

Diseñado para no "alucinar": cada habilidad extraída guarda la evidencia literal
(fragmento del CV) donde fue encontrada, y su nivel de confianza.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from functools import lru_cache

from app.business.skill_catalog import (EDU_LEVELS, EDU_PATTERNS, SHORT_AMBIGUOUS, SOFT_CANON, SOFT_INFERENCE,
                                        TECH_SYNONYMS, canonical_soft, canonical_tech, display_tech, soft_label,
                                        tech_vocabulary)
from app.business.text_utils import clean_display, norm

# ---------------------------------------------------------------------------
# Secciones
# ---------------------------------------------------------------------------
SECTION_KEYS = {
    "soft": ["habilidades blandas", "power skills", "soft skills", "competencias blandas", "habilidades personales",
             "competencias transversales", "habilidades interpersonales", "competencias personales"],
    "skills": ["habilidades tecnicas", "habilidades", "competencias tecnicas", "competencias", "conocimientos",
               "conocimientos tecnicos", "skills", "technical skills", "hard skills", "tecnologias", "herramientas",
               "stack tecnologico", "stack", "aptitudes", "tech stack", "core competencies", "it skills"],
    "experience": ["experiencia laboral", "experiencia profesional", "experiencia", "work experience", "experience",
                   "professional experience", "employment history", "trayectoria", "historial laboral"],
    "education": ["formacion academica", "educacion", "formacion", "estudios", "education", "academic background",
                  "estudios realizados", "academic"],
    "languages": ["idiomas", "languages", "lenguas"],
    "certifications": ["certificaciones", "cursos", "certifications", "licencias y certificaciones", "courses",
                       "cursos y certificaciones", "formacion complementaria"],
    "projects": ["proyectos", "projects", "proyectos destacados"],
    "profile": ["perfil profesional", "perfil", "resumen", "summary", "about me", "acerca de mi", "objetivo",
                "profile", "resumen profesional", "sobre mi"],
    "references": ["referencias", "references", "referencias personales", "referencias laborales"],
    "personal": ["datos personales", "informacion personal", "personal information", "personal details"],
}
_HEADING_INDEX = sorted(((k, sec) for sec, ks in SECTION_KEYS.items() for k in ks), key=lambda x: -len(x[0]))

MONTHS = {
    "ene": 1, "enero": 1, "jan": 1, "january": 1, "feb": 2, "febrero": 2, "february": 2, "mar": 3, "marzo": 3,
    "march": 3, "abr": 4, "abril": 4, "apr": 4, "april": 4, "may": 5, "mayo": 5, "jun": 6, "junio": 6, "june": 6,
    "jul": 7, "julio": 7, "july": 7, "ago": 8, "agosto": 8, "aug": 8, "august": 8, "sep": 9, "sept": 9,
    "septiembre": 9, "setiembre": 9, "september": 9, "oct": 10, "octubre": 10, "october": 10, "nov": 11,
    "noviembre": 11, "november": 11, "dic": 12, "diciembre": 12, "dec": 12, "december": 12,
}
_MONTH_RX = "|".join(sorted(MONTHS, key=len, reverse=True))
_NOW_RX = r"actualidad|actual|presente|present|current|hoy|la fecha|now|today|vigente"
def _date_rx(i: int) -> str:
    return (rf"(?:(?:(?P<m{i}>{_MONTH_RX})\.?\s*(?:de\s+|del\s+)?|(?P<n{i}>\d{{1,2}})\s*[/\-.]\s*)?"
            rf"(?P<y{i}>(?:19|20)\d{{2}}))")


RANGE_RX = re.compile(
    _date_rx(1) + r"\s*(?:-|–|—|a|al|hasta|to|until|/)\s*(?:" + _date_rx(2) + rf"|(?P<now>{_NOW_RX}))",
    re.IGNORECASE,
)

LANGS = {"ingles": "Inglés", "english": "Inglés", "espanol": "Español", "spanish": "Español", "frances": "Francés",
         "french": "Francés", "portugues": "Portugués", "portuguese": "Portugués", "aleman": "Alemán",
         "german": "Alemán", "italiano": "Italiano", "italian": "Italiano", "mandarin": "Mandarín", "chino": "Mandarín",
         "japones": "Japonés", "japanese": "Japonés"}
LANG_LEVEL = r"(a1|a2|b1|b2|c1|c2|basico|basic|intermedio|intermediate|avanzado|advanced|nativo|native|fluido|fluent|bilingue|bilingual|elemental|profesional)"

CO_CITIES = ["bogota", "medellin", "cali", "barranquilla", "cartagena", "bucaramanga", "pereira", "manizales",
             "cucuta", "ibague", "santa marta", "villavicencio", "pasto", "tunja", "neiva", "armenia", "popayan",
             "monteria", "soacha", "chia", "colombia"]


def _fold(text: str) -> str:
    """Minúsculas y sin tildes preservando la longitud (para mapear posiciones al original)."""
    out = []
    for ch in text:
        base = unicodedata.normalize("NFD", ch)[0] if ch else ch
        out.append(base.lower() if len(base.lower()) == 1 else ch)
    return "".join(out)


def _heading_of(line: str) -> tuple[str | None, str]:
    """Si la línea es un encabezado devuelve (sección, contenido restante en la misma línea)."""
    raw = line.strip()
    if not raw or len(raw) > 90:
        return None, ""
    t = norm(raw.replace("|", " "))
    for key, sec in _HEADING_INDEX:
        if t == key:
            return sec, ""
    if ":" in raw:
        head, rest = raw.split(":", 1)
        head_n = norm(head)
        for key, sec in _HEADING_INDEX:
            if head_n == key:
                return sec, rest.strip()
    return None, ""


def split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.splitlines():
        sec, rest = _heading_of(line)
        if sec:
            current = sec
            sections.setdefault(sec, [])
            if rest:
                sections[sec].append(rest)
            continue
        sections.setdefault(current, []).append(line)
    return sections


# ---------------------------------------------------------------------------
# Habilidades
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _tech_regex():
    vocab = tech_vocabulary()
    curated = {norm(a) for c, al in TECH_SYNONYMS.items() for a in al + [c]}
    aliases = sorted((a for a in vocab if len(a) >= 1), key=len, reverse=True)
    body = "|".join(re.escape(a) for a in aliases)
    rx = re.compile(r"(?<![a-z0-9#+])(" + body + r")(?![a-z0-9#+])")
    return rx, vocab, curated


@lru_cache(maxsize=1)
def _soft_regex():
    aliases = sorted({norm(a) for info in SOFT_CANON.values() for a in info["syn"]}, key=len, reverse=True)
    rx = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(a) for a in aliases) + r")(?![a-z0-9])")
    return rx


def _evidence(original: str, start: int, end: int) -> str:
    a = max(0, start - 45)
    b = min(len(original), end + 45)
    snippet = original[a:b].replace("\n", " ")
    return ("…" if a > 0 else "") + clean_display(snippet) + ("…" if b < len(original) else "")


def _add(store: dict, key: str, name: str, confidence: float, evidence: str, source: str) -> None:
    cur = store.get(key)
    if cur is None or confidence > cur["confidence"]:
        store[key] = {"key": key, "name": name, "confidence": round(confidence, 2), "evidence": evidence, "source": source}


def _scan_tech(text: str, store: dict, in_skills: bool) -> None:
    rx, vocab, curated = _tech_regex()
    folded = _fold(text)
    for m in rx.finditer(folded):
        alias = m.group(1)
        canon = vocab.get(alias)
        if not canon:
            continue
        original_token = text[m.start():m.end()]
        is_curated = alias in curated
        if alias in SHORT_AMBIGUOUS or (not is_curated and " " not in alias):
            if not in_skills:
                continue
            if alias in {"r", "c", "go"} and original_token not in {"R", "C", "Go", "GO", "Golang"}:
                continue
        if canonical_soft(alias):
            continue
        conf = 0.95 if in_skills else (0.85 if is_curated else 0.75)
        _add(store, canon, display_tech(canon), conf, _evidence(text, m.start(), m.end()),
             "Sección de habilidades" if in_skills else "Experiencia / perfil")


def _scan_soft(text: str, store: dict, in_soft: bool) -> None:
    rx = _soft_regex()
    folded = _fold(text)
    for m in rx.finditer(folded):
        key = canonical_soft(m.group(1))
        if not key:
            continue
        _add(store, key, soft_label(key), 0.95 if in_soft else 0.8, _evidence(text, m.start(), m.end()),
             "Declarada en el CV" if in_soft else "Mencionada en el CV")


def _infer_soft(text: str, store: dict) -> None:
    folded = _fold(text)
    for key, patterns in SOFT_INFERENCE.items():
        if key in store:
            continue
        for p in patterns:
            m = re.search(p, folded)
            if m:
                _add(store, key, soft_label(key), 0.6, _evidence(text, m.start(), m.end()), "Inferida de logros")
                break


def _declared_items(lines: list[str]) -> list[str]:
    items = []
    for line in lines:
        line = re.sub(r"^[\s\-–•▪●►*·]+", "", line)
        if ":" in line and len(line.split(":")[0]) < 30:
            line = line.split(":", 1)[1]
        for part in re.split(r"[,;|•·/]|\s{3,}|\s-\s", line):
            p = clean_display(part)
            if 1 <= len(p) <= 40 and 1 <= len(p.split()) <= 4 and not re.search(r"\d{4}", p):
                items.append(p)
    return items


def extract_skills(text: str, sections: dict[str, list[str]], declared_tech: list[str] | None = None,
                   declared_soft: list[str] | None = None) -> tuple[list[dict], list[dict]]:
    tech: dict = {}
    soft: dict = {}
    skills_text = "\n".join(sections.get("skills", []))
    soft_text = "\n".join(sections.get("soft", []))
    other_text = "\n".join(l for sec, ls in sections.items() if sec not in {"skills", "soft", "references", "personal"} for l in ls)

    _scan_tech(skills_text, tech, in_skills=True)
    _scan_tech(soft_text, tech, in_skills=True)
    _scan_tech(other_text, tech, in_skills=False)
    _scan_soft(soft_text, soft, in_soft=True)
    _scan_soft(skills_text, soft, in_soft=True)
    _scan_soft(other_text, soft, in_soft=False)
    _infer_soft("\n".join(sections.get("experience", []) + sections.get("projects", [])), soft)

    # Ítems declarados explícitamente en listas de habilidades (aunque no estén en el vocabulario del dataset)
    vocab = tech_vocabulary()
    for item in (declared_tech or []) + _declared_items(sections.get("skills", [])):
        sk = canonical_soft(item)
        if sk:
            _add(soft, sk, soft_label(sk), 0.95, item, "Declarada en el CV")
            continue
        key = canonical_tech(item)
        if len(key) < 2 and key not in {"r", "c"}:
            continue
        if key in {"y", "and", "otros", "others", "etc", "basico", "intermedio", "avanzado"}:
            continue
        name = display_tech(key) if key in vocab or key in TECH_SYNONYMS else clean_display(item)
        _add(tech, key, name, 0.9, item, "Declarada en el CV")
    for item in (declared_soft or []) + _declared_items(sections.get("soft", [])):
        sk = canonical_soft(item)
        key = sk or norm(item)
        if not key or len(key) < 3:
            continue
        _add(soft, key, soft_label(sk) if sk else clean_display(item).capitalize(), 0.9, item, "Declarada en el CV")

    tech_list = sorted(tech.values(), key=lambda s: (-s["confidence"], s["name"]))
    soft_list = sorted(soft.values(), key=lambda s: (-s["confidence"], s["name"]))
    return tech_list[:60], soft_list[:25]


# ---------------------------------------------------------------------------
# Experiencia, educación, idiomas
# ---------------------------------------------------------------------------
def _ym(month: str | None, num: str | None, year: str) -> tuple[int, int]:
    m = 1
    if month:
        m = MONTHS.get(norm(month).rstrip("."), 1)
    elif num and 1 <= int(num) <= 12:
        m = int(num)
    return int(year), m


def parse_ranges(lines: list[str]) -> list[dict]:
    entries = []
    today = date.today()
    for idx, line in enumerate(lines):
        folded = _fold(line)
        for m in RANGE_RX.finditer(folded):
            y1, m1 = _ym(m.group("m1"), m.group("n1"), m.group("y1"))
            if m.group("now"):
                y2, m2 = today.year, today.month
            else:
                y2, m2 = _ym(m.group("m2"), m.group("n2"), m.group("y2"))
            start, end = y1 * 12 + m1, y2 * 12 + m2
            if end < start or y1 < 1970 or end > today.year * 12 + today.month + 1:
                continue
            role = clean_display(line[:m.start()] + " " + line[m.end():]).strip(" |,-–()")
            if len(role) < 4 and idx > 0:
                role = clean_display(lines[idx - 1])
            if len(role) < 4 and idx + 1 < len(lines):
                role = clean_display(lines[idx + 1])
            entries.append({"role": role[:140], "period": clean_display(line[m.start():m.end()]),
                            "start": start, "end": end, "years": round((end - start) / 12, 1)})
    return entries


def total_years(entries: list[dict]) -> float:
    spans = sorted((e["start"], e["end"]) for e in entries)
    merged: list[list[int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    months = sum(e - s for s, e in merged)
    return round(months / 12, 1)


def stated_years(text: str) -> float:
    t = norm(text)
    vals = [float(m.group(1).replace(",", ".")) for m in
            re.finditer(r"(\d{1,2}(?:[.,]\d)?)\s*\+?\s*(?:anos|years)\s+(?:de\s+|of\s+)?(?:professional\s+)?experien", t)]
    vals = [v for v in vals if 0 < v <= 45]
    return max(vals) if vals else 0.0


def education_from(lines: list[str], full_text: str) -> tuple[list[dict], int]:
    entries, best = [], 0
    for line in lines:
        l = clean_display(line)
        if len(l) < 4:
            continue
        lvl = max([lv for lv, p in EDU_PATTERNS if re.search(p, norm(l))] or [0])
        if lvl == 4 and re.search(r"\b(estudiante|en curso|cursando|student|current|semestre)\b", norm(l)):
            lvl = 3 if lvl > 3 else lvl  # pregrado en curso: aún no titulado
        best = max(best, lvl)
        entries.append({"text": l[:160], "level": lvl})
    if best == 0:
        lv = [lv for lv, p in EDU_PATTERNS if re.search(p, norm(full_text))]
        best = max(lv) if lv else 0
        if best == 1 and lv:
            best = 1
    return entries[:8], best


def languages_from(text: str) -> list[dict]:
    out, seen = [], set()
    folded = _fold(text)
    for key, label in LANGS.items():
        for m in re.finditer(rf"\b{key}\b[^\n]{{0,25}}", folded):
            if label in seen:
                continue
            lv = re.search(LANG_LEVEL, m.group(0))
            seen.add(label)
            out.append({"language": label, "level": lv.group(1).upper() if lv and len(lv.group(1)) == 2 else (lv.group(1).capitalize() if lv else "No indicado")})
    return out


# ---------------------------------------------------------------------------
# Identificación de contacto (se cifra en BD; no participa en el matching)
# ---------------------------------------------------------------------------
EMAIL_RX = re.compile(r"[\w\.\-+]+@[\w\-]+\.[\w\.\-]+")
PHONE_RX = re.compile(r"(?:\+?57[\s\-]?)?(?:\(?\d{3}\)?[\s\-]?)\d{3}[\s\-]?\d{4}\b|\+\d{1,3}[\s\-]?\d[\d\s\-]{7,12}\d")


def contact_from(text: str, header: list[str]) -> dict:
    email = EMAIL_RX.search(text)
    phone = PHONE_RX.search(text)
    name, headline, location = "", "", ""
    candidates = [clean_display(l) for l in header if clean_display(l)] or [clean_display(l) for l in text.splitlines()[:8] if clean_display(l)]
    for line in candidates[:6]:
        if EMAIL_RX.search(line) or PHONE_RX.search(line) or "http" in line.lower():
            continue
        words = line.split()
        if not name and 2 <= len(words) <= 5 and all(re.match(r"^[A-Za-zÁÉÍÓÚÑáéíóúñÜü\.'\-]+$", w) for w in words) \
                and not _heading_of(line)[0]:
            name = line.title() if line.isupper() else line
            continue
        if name and not headline and 3 <= len(line) <= 120:
            headline = line
    for line in candidates[:12] + text.splitlines()[:15]:
        f = _fold(line)
        if any(re.search(rf"\b{c}\b", f) for c in CO_CITIES) and len(line) < 80:
            location = clean_display(EMAIL_RX.sub("", PHONE_RX.sub("", line))).strip(" |,-")
            break
    return {"name": name, "email": email.group(0) if email else "", "phone": phone.group(0).strip() if phone else "",
            "location": location[:80], "headline": headline[:160]}


def ym_str(month_index: int) -> str:
    """Índice año*12+mes → 'AAAA-MM' (formato de <input type=month>)."""
    if not month_index:
        return ""
    y, m = (month_index - 1) // 12, (month_index - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"


def experience_view(e: dict) -> dict:
    today = date.today()
    now_idx = today.year * 12 + today.month
    end = e.get("end") or 0
    role, company = e.get("role", ""), e.get("company", "")
    if role and not company:  # "Data Engineer - Banco Andino" → cargo + empresa
        parts = re.split(r"\s+(?:-|–|\||@|at|en)\s+", role, maxsplit=1)
        if len(parts) == 2 and all(len(x.strip()) >= 2 for x in parts):
            role, company = parts[0].strip(), parts[1].strip()
    return {"role": role, "company": company, "period": e.get("period", ""),
            "years": e.get("years", 0), "start": ym_str(e.get("start") or 0),
            "end": "" if end >= now_idx else ym_str(end), "current": bool(end and end >= now_idx),
            "source": e.get("source", "Extraída del CV")}


def parse_text(text: str, declared: dict | None = None) -> dict:
    """Texto plano de un CV (ya sin datos sensibles) → perfil estructurado."""
    declared = declared or {}
    sections = split_sections(text)
    contact = contact_from(text, sections.get("header", []))
    tech, soft = extract_skills(text, sections, declared.get("tech"), declared.get("soft"))

    exp_lines = sections.get("experience") or [l for sec, ls in sections.items() if sec not in {"education", "certifications"} for l in ls]
    entries = declared.get("experience") or parse_ranges(exp_lines)
    years = total_years(entries) if entries and "start" in entries[0] else float(declared.get("years", 0) or 0)
    years = max(years, stated_years(text) if years == 0 else 0)
    edu_entries, edu_level = education_from(declared.get("education_lines") or sections.get("education", []), text)

    summary = " ".join(clean_display(l) for l in sections.get("profile", []) if clean_display(l))[:700]
    certs = [clean_display(l) for l in sections.get("certifications", []) if len(clean_display(l)) > 4][:12]
    langs = languages_from("\n".join(sections.get("languages", [])) or text)

    filled = sum(bool(x) for x in [contact["name"], contact["email"], tech, soft, entries, edu_entries or edu_level])
    warnings = []
    if not tech:
        warnings.append("No se identificaron habilidades técnicas; revise y edite el perfil.")
    if not entries and not years:
        warnings.append("No se identificaron fechas de experiencia laboral.")
    if not soft:
        warnings.append("No se identificaron power skills explícitas.")
    return {
        **contact,
        "headline": declared.get("headline") or contact["headline"],
        "summary": declared.get("summary") or summary,
        "tech_skills": tech,
        "soft_skills": soft,
        "experience": [experience_view(e) for e in entries][:12],
        "years_experience": round(years, 1),
        "education": edu_entries,
        "education_level": edu_level,
        "education_label": EDU_LEVELS.get(edu_level, "No identificado"),
        "languages": declared.get("languages") or langs,
        "certifications": declared.get("certifications") or certs,
        "references_omitted": bool(sections.get("references")),
        "quality": {"completeness": round(filled / 6 * 100), "warnings": warnings,
                    "sections": [s for s in sections if s != "header" and sections[s]]},
    }
