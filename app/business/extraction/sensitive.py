"""Detección y descarte de datos sensibles / irrelevantes para el matching.

Ley 1581 de 2012 (art. 5): datos sensibles son los que afectan la intimidad o pueden
generar discriminación (origen, orientación política, religión, salud, vida sexual,
biométricos). RGPD art. 5.1.c: minimización. Estos datos NO se usan en el matching ni se
almacenan: sólo se registra la *categoría* detectada para transparencia con el titular.
"""
from __future__ import annotations

import re

SENSITIVE_RULES: list[tuple[str, str]] = [
    ("Documento de identidad", r"(?<![a-z])(c\.\s?c\.?|cc|cedula( de ciudadania)?|cédula( de ciudadanía)?|documento( de identidad)?|"
                               r"dni|pasaporte|passport|tarjeta de identidad|t\.\s?i\.|nit|ssn|social security)(?![a-z])"
                               r"\s*(no\.?|n[°º]|#|:|-)?\s*\d[\d\.\s\-]{5,}"),
    ("Fecha de nacimiento", r"\b(fecha de nacimiento|f\. de nacimiento|date of birth|birth ?date|nacid[oa] (el|en)|born on|dob)\b"),
    ("Edad", r"\b(edad|age)\s*[:\-]\s*\d{1,2}\b|\b\d{2}\s*(anos|años) de edad\b|\b\d{2}\s*years old\b"),
    ("Estado civil", r"\b(estado civil|marital status|solter[oa]|casad[oa]|union libre|unión libre|divorciad[oa]|viud[oa])\b"),
    ("Sexo / género", r"\b(sexo|genero|género|gender|sex)\s*[:\-]"),
    ("Religión", r"\b(religion|religión|creencia religiosa|credo)\s*[:\-]"),
    ("Origen / nacionalidad", r"\b(nacionalidad|nationality|lugar de nacimiento|place of birth|etnia|ethnicity|raza)\b"),
    ("Datos de salud", r"\b(grupo sangu[ií]neo|tipo de sangre|blood type|\brh\b\s*[:\-]?\s*[abo]{1,2}\s*[+\-]|eps\s*[:\-]|discapacidad|disability|"
                       r"condici[oó]n m[eé]dica\s*[:\-]|enfermedad(es)?\s*[:\-])"),
    ("Situación militar", r"\b(libreta militar|military card|servicio militar)\b"),
    ("Afiliación política o sindical", r"\b(partido pol[ií]tico|afiliaci[oó]n pol[ií]tica|sindicato|union member)\b"),
    ("Dirección de residencia", r"\b(direcci[oó]n( de residencia)?|address|domicilio|barrio)\s*[:\-]"),
    ("Información familiar", r"\b(n[uú]mero de hijos|hijos\s*[:\-]|children\s*[:\-]|c[oó]nyuge|spouse)\b"),
]

JSON_SENSITIVE_KEYS = {
    "fecha_nacimiento": "Fecha de nacimiento", "fechanacimiento": "Fecha de nacimiento", "birthdate": "Fecha de nacimiento",
    "dateofbirth": "Fecha de nacimiento", "dob": "Fecha de nacimiento", "edad": "Edad", "age": "Edad",
    "genero": "Sexo / género", "gender": "Sexo / género", "sexo": "Sexo / género", "sex": "Sexo / género",
    "estado_civil": "Estado civil", "estadocivil": "Estado civil", "maritalstatus": "Estado civil",
    "documento": "Documento de identidad", "cedula": "Documento de identidad", "dni": "Documento de identidad",
    "passport": "Documento de identidad", "pasaporte": "Documento de identidad", "identificacion": "Documento de identidad",
    "religion": "Religión", "nacionalidad": "Origen / nacionalidad", "nationality": "Origen / nacionalidad",
    "etnia": "Origen / nacionalidad", "foto": "Fotografía", "photo": "Fotografía", "picture": "Fotografía", "image": "Fotografía",
    "direccion": "Dirección de residencia", "address": "Dirección de residencia", "tipo_sangre": "Datos de salud",
    "rh": "Datos de salud", "eps": "Datos de salud", "salud": "Datos de salud", "discapacidad": "Datos de salud",
    "libreta_militar": "Situación militar", "referencias": "Referencias de terceros", "references": "Referencias de terceros",
    "hijos": "Información familiar",
}

_COMPILED = [(cat, re.compile(p, re.IGNORECASE)) for cat, p in SENSITIVE_RULES]


def redact_sensitive(text: str) -> tuple[str, list[str]]:
    """Devuelve el texto sin las líneas sensibles y la lista de categorías detectadas."""
    found: list[str] = []
    kept: list[str] = []
    for line in text.splitlines():
        hit = None
        for cat, rx in _COMPILED:
            if rx.search(line):
                hit = cat
                break
        if hit:
            if hit not in found:
                found.append(hit)
            kept.append("")  # se conserva la estructura de líneas
        else:
            kept.append(line)
    return "\n".join(kept), found


def redact_for_external(text: str) -> str:
    """Seudonimiza contacto antes de cualquier envío a un servicio externo (minimización)."""
    t = re.sub(r"[\w\.\-+]+@[\w\-]+\.[\w\.\-]+", "[EMAIL]", text)
    t = re.sub(r"(\+?\d[\d\s\-()]{7,}\d)", "[TELEFONO]", t)
    t = re.sub(r"https?://\S+|www\.\S+", "[URL]", t)
    return t
