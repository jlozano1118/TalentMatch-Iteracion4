"""Lectura de CV en JSON (JSON Resume, formatos ATS en español o estructuras libres)."""
from __future__ import annotations

import json
import re
from typing import Any

from app.business.extraction.cv_parser import MONTHS
from app.business.extraction.sensitive import JSON_SENSITIVE_KEYS
from app.business.text_utils import clean_display, norm

SKILL_KEY = re.compile(r"(skill|habilidad|tecnolog|herramient|competenc|conocimiento|stack|keywords|aptitud)")
SOFT_KEY = re.compile(r"(soft|blanda|power|transversal|personal_skill|interpersonal)")
EXP_KEY = re.compile(r"^(work|experience|experiencia|experiencias|experiencia_laboral|employment|trabajos|empleos|historial_laboral|trayectoria)$")
EDU_KEY = re.compile(r"^(education|educacion|formacion|formacion_academica|estudios)$")
LANG_KEY = re.compile(r"^(languages|idiomas|lenguas)$")
CERT_KEY = re.compile(r"^(certificates|certifications|certificaciones|cursos|courses|awards)$")


def _k(key: str) -> str:
    return norm(str(key)).replace(" ", "_").replace("-", "_")


def _parse_date(value: Any) -> tuple[int, int] | None:
    if not value:
        return None
    s = norm(str(value))
    if re.search(r"actual|presente|present|current|hoy|now", s):
        from datetime import date

        d = date.today()
        return d.year, d.month
    m = re.search(r"((?:19|20)\d{2})[\-/\.](\d{1,2})", s)
    if m:
        return int(m.group(1)), max(1, min(12, int(m.group(2))))
    m = re.search(r"(\d{1,2})[\-/\.]((?:19|20)\d{2})", s)
    if m:
        return int(m.group(2)), max(1, min(12, int(m.group(1))))
    m = re.search(r"([a-z]{3,10})\.?\s*(?:de\s+)?((?:19|20)\d{2})", s)
    if m and m.group(1) in MONTHS:
        return int(m.group(2)), MONTHS[m.group(1)]
    m = re.search(r"((?:19|20)\d{2})", s)
    if m:
        return int(m.group(1)), 1
    return None


def _first(d: dict, *names) -> Any:
    keys = {_k(k): v for k, v in d.items()}
    for n in names:
        if n in keys and keys[n] not in (None, "", []):
            return keys[n]
    return None


def _strings(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        out.extend(p.strip() for p in re.split(r"[,;|\n]", value) if p.strip())
    elif isinstance(value, list):
        for v in value:
            out.extend(_strings(v))
    elif isinstance(value, dict):
        name = _first(value, "name", "nombre", "skill", "habilidad", "titulo", "language", "idioma")
        if name:
            out.extend(_strings(name))
        kw = _first(value, "keywords", "items", "tecnologias", "lista", "detalle")
        if kw:
            out.extend(_strings(kw))
    return out


def _flatten(value: Any, depth: int = 0) -> list[str]:
    if depth > 6:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float)):
        return []
    if isinstance(value, list):
        return [s for v in value for s in _flatten(v, depth + 1)]
    if isinstance(value, dict):
        return [s for k, v in value.items() if _k(k) not in JSON_SENSITIVE_KEYS for s in _flatten(v, depth + 1)]
    return []


def read_json(data: bytes) -> tuple[str, dict, list[str]]:
    """Devuelve (texto equivalente, campos declarados, categorías sensibles descartadas)."""
    try:
        doc = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"El archivo JSON no es válido: {exc}") from exc
    if isinstance(doc, list) and doc and isinstance(doc[0], dict):
        doc = doc[0]
    if not isinstance(doc, dict):
        raise ValueError("El JSON debe contener un objeto con la hoja de vida.")

    sensitive: list[str] = []
    tech, soft, exp_entries, edu_lines, langs, certs = [], [], [], [], [], []
    basics: dict = {}

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                k = _k(key)
                if k in JSON_SENSITIVE_KEYS:
                    cat = JSON_SENSITIVE_KEYS[k]
                    if cat not in sensitive:
                        sensitive.append(cat)
                    continue
                if k in {"basics", "datos_basicos", "informacion_basica", "candidato", "perfil_personal", "contacto", "datos_personales", "personal"} and isinstance(val, dict):
                    basics.update(val)
                    walk(val, k)
                    continue
                if EXP_KEY.match(k) and isinstance(val, list):
                    for e in val:
                        if isinstance(e, dict):
                            exp_entries.append(e)
                    continue
                if EDU_KEY.match(k):
                    for e in (val if isinstance(val, list) else [val]):
                        if isinstance(e, dict):
                            parts = [str(_first(e, "studytype", "nivel", "tipo", "degree", "grado") or ""),
                                     str(_first(e, "area", "titulo", "title", "programa", "carrera") or ""),
                                     str(_first(e, "institution", "institucion", "universidad", "school") or ""),
                                     str(_first(e, "estado", "status") or "")]
                            edu_lines.append(" - ".join(p for p in parts if p))
                        elif isinstance(e, str):
                            edu_lines.append(e)
                    continue
                if LANG_KEY.match(k):
                    for e in (val if isinstance(val, list) else [val]):
                        if isinstance(e, dict):
                            langs.append({"language": clean_display(str(_first(e, "language", "idioma", "name", "nombre") or "")),
                                          "level": clean_display(str(_first(e, "fluency", "nivel", "level") or "No indicado"))})
                        elif isinstance(e, str):
                            langs.append({"language": clean_display(e), "level": "No indicado"})
                    continue
                if CERT_KEY.match(k):
                    certs.extend(clean_display(s) for s in _strings(val))
                    continue
                if SKILL_KEY.search(k) and not isinstance(val, (int, float)):
                    if SOFT_KEY.search(k):
                        soft.extend(_strings(val))
                    elif isinstance(val, dict) and not _first(val, "name", "nombre"):
                        for sub_k, sub_v in val.items():
                            (soft if SOFT_KEY.search(_k(sub_k)) else tech).extend(_strings(sub_v))
                    else:
                        tech.extend(_strings(val))
                    continue
                walk(val, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, path)

    walk(doc)
    if not basics:
        basics = doc

    experience, months_total = [], []
    for e in exp_entries:
        role = _first(e, "position", "cargo", "puesto", "rol", "title", "titulo") or ""
        company = _first(e, "name", "company", "empresa", "organizacion", "organization") or ""
        start = _parse_date(_first(e, "startdate", "start_date", "fecha_inicio", "inicio", "desde", "start", "from"))
        end = _parse_date(_first(e, "enddate", "end_date", "fecha_fin", "fin", "hasta", "end", "to")) or _parse_date("actual")
        period = _first(e, "periodo", "period", "fechas")
        if not start and period:
            m = re.findall(r"(?:19|20)\d{2}", str(period))
            if m:
                start = (int(m[0]), 1)
                end = (int(m[1]), 12) if len(m) > 1 else _parse_date("actual")
        entry = {"role": clean_display(" · ".join(x for x in [str(role), str(company)] if x))[:140], "period": "", "years": 0.0}
        if start and end:
            s, f = start[0] * 12 + start[1], end[0] * 12 + end[1]
            if f >= s:
                entry.update({"start": s, "end": f, "years": round((f - s) / 12, 1),
                              "period": f"{start[1]:02d}/{start[0]} – {end[1]:02d}/{end[0]}"})
        if "start" not in entry:
            entry.update({"start": 0, "end": 0})
        experience.append(entry)
        # habilidades y logros dentro de la experiencia entran al texto para inferencia
    years_decl = _first(doc, "anos_experiencia", "years_experience", "experiencia_anos", "total_experiencia")

    name = _first(basics, "name", "nombre", "nombre_completo", "full_name") or ""
    if isinstance(name, dict):
        name = " ".join(str(v) for v in name.values())
    declared = {
        "tech": tech, "soft": soft,
        "experience": [e for e in experience if e.get("end")] or None,
        "years": years_decl,
        "education_lines": edu_lines,
        "languages": [l for l in langs if l["language"]] or None,
        "certifications": [c for c in certs if c][:12] or None,
        "headline": clean_display(str(_first(basics, "label", "cargo", "titulo", "title", "headline", "profesion", "cargo_actual") or "")),
        "summary": clean_display(str(_first(basics, "summary", "resumen", "perfil", "perfil_profesional", "about", "objetivo")
                                     or _first(doc, "summary", "resumen", "perfil", "perfil_profesional") or ""))[:700],
    }
    email = _first(basics, "email", "correo", "correo_electronico", "mail") or ""
    phone = _first(basics, "phone", "telefono", "celular", "movil") or ""
    location = _first(basics, "location", "ubicacion", "ciudad", "city") or ""
    if isinstance(location, dict):
        location = ", ".join(str(v) for k, v in location.items() if _k(k) in {"city", "ciudad", "region", "country", "pais", "countrycode"})

    lines = [str(name), str(declared["headline"]), str(email), str(phone), str(location), ""]
    if declared["summary"]:
        lines += ["PERFIL", declared["summary"], ""]
    lines += ["EXPERIENCIA"]
    for e in exp_entries:
        lines += [s for s in _flatten(e)]
    lines += ["", "EDUCACIÓN"] + edu_lines
    if tech:
        lines += ["", "HABILIDADES TÉCNICAS", ", ".join(tech)]
    if soft:
        lines += ["", "HABILIDADES BLANDAS", ", ".join(soft)]
    text = "\n".join(lines)
    declared["contact"] = {"name": clean_display(str(name)), "email": str(email), "phone": str(phone), "location": clean_display(str(location))}
    return text, declared, sensitive
