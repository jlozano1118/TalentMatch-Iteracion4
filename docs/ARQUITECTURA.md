# Arquitectura · TalentMatch iteración 4

## Capas

| Capa | Carpeta | Responsabilidad | Depende de |
|---|---|---|---|
| Presentación (UI) | `app/presentation` | Routers REST de FastAPI, validación con Pydantic, serialización a vistas, SPA animada (HTML/CSS/JS) | Lógica de negocio |
| Lógica de negocio | `app/business` | Extracción de CV, descarte de datos sensibles, matching, plan de capacitación, consentimiento, evaluación ética, autenticación | Persistencia |
| Persistencia | `app/persistence` | Repositorios (consultas SQLAlchemy), lectura de los datasets, cifrado en reposo | Base de datos |
| Base de datos | `app/database` | Motor SQLite, modelo ORM, esquema, usuarios autorizados y proyectos (datos semilla) | — |

## Flujo de un análisis

```
CV (PDF texto | PDF escaneado | imagen | JSON)
   │  POST /api/candidates/analyze  (archivo + autorización del titular)
   ▼
privacy_service.register_consent  ──►  tabla consents (versión, finalidades, fecha, responsable)
   ▼
document_reader / json_reader     ──►  texto (OCR Tesseract si es escaneado o imagen)
   ▼
sensitive.redact_sensitive        ──►  se descartan identificación, nacimiento, edad, género, salud, foto…
   ▼
cv_parser.parse_text              ──►  habilidades técnicas y power skills con evidencia literal,
                                       experiencia (rangos de fechas fusionados), formación, idiomas
   ▼
matching_service.score_role × 33 cargos  ──►  tablas matches + project_matches
quick_market_score × 3.000 ofertas       ──►  tabla market_matches (top 10, re-puntuado)
   ▼
training_service.build_plan (mejor cargo) ──►  tablas training_plans + plan_items
   ▼
Respuesta a la SPA (sin JSON ni Markdown visibles para el usuario)
```

Al dar clic en otro cargo (`GET /api/candidates/{id}/roles/{role_id}`) se marca como consultado y se genera y guarda su plan de capacitación.

## Modelo de matching

```
puntaje = w_tec · técnico + w_pow · power + w_exp · experiencia + w_edu · educación      (Σw = 1)
```

- **Técnico / power:** promedio ponderado del crédito por requisito: 1.0 coincidencia exacta (con sinónimos ES↔EN), 0.85 casi idéntica, 0.7 contenida, 0.6 habilidad relacionada (p. ej. PostgreSQL → SQL). Requisitos frecuentes en el dataset pesan 1.0; los muy específicos 0.6.
- **Experiencia:** `min(1, años acreditados / años exigidos)`; si la oferta no fija años se toma 1.
- **Educación:** 1.0 si cumple, 0.7 a un nivel, 0.35 más lejos, 0.4 si no se identificó.
- **Pesos por defecto según la naturaleza del rol:** técnico especializado 55/20/17/8, híbrido 45/30/17/8, orientado a negocio 35/40/17/8; los cargos de liderazgo trasladan 10 puntos de técnico a power. Talento Humano puede ajustarlos por análisis o como perfil del cargo.

## Plan de capacitación

TF-IDF (bigramas) sobre título + habilidades + descripción de 11.550 cursos con calificación **> 4.0**. Para cada brecha se elige el mejor curso por plataforma combinando relevancia y calificación, exigiendo que el término clave aparezca en el título (o en las habilidades con alta similitud). Horas: Udemy reales; Coursera estimadas por nivel (marcadas como *estimado*).

## Seguridad

- 4 usuarios autorizados; contraseñas con bcrypt (coste 12); usuarios no autorizados se eliminan al iniciar.
- JWT HS256 en cookie `HttpOnly`, `SameSite=Strict`; bloqueo de 15 min tras 5 intentos; respuesta de tiempo constante ante usuarios inexistentes.
- Cifrado Fernet de nombre, correo, teléfono y ubicación; contacto enmascarado en la UI, revelarlo queda auditado.
- Cabeceras CSP, `X-Frame-Options`, `nosniff`, `no-referrer`; `Cache-Control: no-store` en la API.
- Todo texto proveniente de un CV se escapa en el cliente; los enlaces a cursos sólo aceptan http(s) y abren con `rel="noopener noreferrer"`.
- El archivo original no se guarda: sólo su huella SHA-256 (evita duplicados).

## Tablas

`users`, `consents`, `candidates`, `projects`, `roles`, `matches`, `project_matches`, `market_matches`, `training_plans`, `plan_items`, `hr_decisions`, `audit_logs`. La supresión de un candidato borra en cascada todo lo asociado y marca la autorización como revocada.
