# Tarjeta de Evaluación Ética · TalentMatch (iteración 4)

Basada en la herramienta de la Unidad 5 (inspirada en *Model Cards* y *Datasheets for Datasets*).

## 1. ¿Qué hace el sistema?
- **Propósito:** apoyar a Talento Humano en la movilidad interna: comparar el perfil de un colaborador con los cargos de los proyectos y recomendar capacitación para cerrar brechas.
- **Usuarios:** analistas de Talento Humano (4 cuentas autorizadas `@talentmatch.co`).
- **Personas afectadas:** colaboradores cuyas hojas de vida se analizan.
- **Flujo de decisión:** CV → extracción con evidencia → puntaje explicable → **decisión humana justificada**. El sistema nunca asigna automáticamente.

## 2. ¿Qué datos usa?
| Fuente | Origen | Sesgos posibles | Consentimiento / privacidad |
|---|---|---|---|
| CV de colaboradores | Cargados por Talento Humano | Calidad desigual (escaneados, formatos) | Autorización previa, expresa e informada por finalidad (Ley 1581). Datos sensibles descartados. |
| JobsDatasetProcessed.csv (3.000 ofertas, 25 categorías) | Dataset público de ofertas de EE. UU. | Idioma inglés, mercado estadounidense, sesgo hacia perfiles senior | Sin datos personales |
| Coursera.csv (3.522) y Udemy_Courses.xlsx (9.968) | Catálogos públicos | Predominio de cursos en inglés y de pago | Sin datos personales |

## 3. ¿Cómo se evaluó?
Métricas definidas antes de construir y medidas sobre un conjunto etiquetado de 5 CV de prueba (PDF texto, PDF escaneado, imagen y dos JSON):

| Métrica | Resultado | Línea base |
|---|---|---|
| Precisión extracción técnica | ≈ 84 % | — |
| Exhaustividad extracción técnica | ≈ 98 % | 72 % (sólo partir la lista de habilidades) |
| Precisión / exhaustividad power skills | ≈ 95 % / 100 % | — |
| Años de experiencia y nivel educativo correctos | 5/5 y 5/5 | — |
| Datos sensibles descartados | 5/5 | — |

**Indicador de equidad:** brecha del puntaje promedio según el tipo de CV (texto, escaneado, imagen, JSON); alerta si supera 10 puntos.
**Indicador de impacto social:** porcentaje de colaboradores con al menos un cargo ≥ 60 % (movilidad interna visible).
**Limitaciones conocidas:** conjunto de prueba pequeño y sintético; el OCR sin el paquete de español pierde tildes; los requisitos muy específicos de las ofertas (p. ej. normas regulatorias de EE. UU.) bajan el puntaje técnico. Pendiente validar con usuarios reales de Talento Humano (Unidad 6).

Las métricas se recalculan en vivo en la vista *Ética y privacidad* y con `python -m scripts.evaluate`.

## 4. ¿Qué riesgos tiene y cómo se mitigan?
| Riesgo | Dónde | Mitigación |
|---|---|---|
| Alucinación | Extracción de habilidades | Parser determinista con evidencia literal; IA externa opcional sólo acepta lo verificable en el texto. |
| Sesgo / discriminación | Puntaje | Sólo variables laborales; se descartan edad, género, foto, estado civil, origen, religión y salud; indicador de equidad por fuente. |
| Sobre-confianza en el puntaje | Decisión | Supervisión humana obligatoria con justificación ≥ 15 caracteres; aviso de sistema de alto riesgo. |
| Errores de extracción | Perfil | Edición (rectificación) del perfil con recálculo automático. |
| Reidentificación | Bitácora y reportes | Seudónimo TM-XXXX; contacto cifrado y enmascarado. |
| Datos en el prompt | IA externa | Desactivada por defecto; casilla independiente; anonimización previa. |
| Impacto organizacional | Uso del sistema | Enfoque de crecimiento: cada brecha produce un plan de capacitación, no una exclusión. |

**Riesgo crítico:** una recomendación errónea podría afectar la trayectoria de un colaborador.
**Mitigación principal:** explicación completa del puntaje + decisión humana registrada + derecho de rectificación y supresión.

## 5. Cumplimiento normativo
- **Ley 1581 de 2012 y Decreto 1377 de 2013:** autorización por finalidad con prueba, derechos de conocer, actualizar, rectificar, suprimir y revocar; datos sensibles excluidos; política de tratamiento visible.
- **RGPD:** minimización (no se guarda el archivo), limitación del plazo (retención configurable, 365 días por defecto, con purga automática), portabilidad (reporte descargable), derecho al olvido, privacidad por diseño, no decisiones basadas únicamente en tratamiento automatizado (art. 22).
- **AI Act (UE) 2024/1689:** los sistemas de IA para selección y gestión de trabajadores son de **alto riesgo** (Anexo III, punto 4). Se implementan supervisión humana, transparencia hacia el usuario, registro de eventos (bitácora), gestión de calidad de datos y evaluación documentada. No se usan prácticas prohibidas (reconocimiento de emociones en el trabajo, categorización biométrica).
