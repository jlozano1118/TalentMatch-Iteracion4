"""Proyectos internos de la empresa (único dato "quemado" del sistema).

Cada cargo referencia una fila REAL de JobsDatasetProcessed.csv mediante su columna ID.
El título, habilidades técnicas, power skills, educación y experiencia del cargo se
leen del dataset al sembrar la base de datos; aquí sólo se define a qué proyecto pertenece.
"""

PROJECTS = [
    {
        "code": "PRJ-01", "name": "Plataforma Omnicanal 2.0", "area": "Banca Digital", "status": "Activo",
        "start": "Mar 2026", "end": "Dic 2026",
        "description": "Rediseño completo de la experiencia digital del cliente en todos los canales (app móvil, web y cajeros).",
        "job_ids": [9072, 8336, 7372, 8869],
    },
    {
        "code": "PRJ-02", "name": "DataLake Corporativo", "area": "Datos & Analytics", "status": "Activo",
        "start": "Ene 2026", "end": "Sep 2026",
        "description": "Construcción del repositorio centralizado de datos con capacidades de analítica avanzada e IA.",
        "job_ids": [1276, 5514, 1028, 5102, 5808],
    },
    {
        "code": "PRJ-03", "name": "API Banking Gateway", "area": "Open Banking", "status": "Próximo",
        "start": "Oct 2026", "end": "Mar 2027",
        "description": "Gateway unificado de APIs para habilitar el ecosistema Open Banking y alianzas con fintechs.",
        "job_ids": [7458, 9974, 6359, 9129],
    },
    {
        "code": "PRJ-04", "name": "Motor de Riesgo Crediticio IA", "area": "Inteligencia Artificial", "status": "Activo",
        "start": "Feb 2026", "end": "Nov 2026",
        "description": "Modelos predictivos explicables para el scoring de riesgo crediticio y la detección temprana de mora.",
        "job_ids": [340, 3396, 1756, 274],
    },
    {
        "code": "PRJ-05", "name": "Centro de Inteligencia de Negocio", "area": "Business Intelligence", "status": "Activo",
        "start": "Abr 2026", "end": "Feb 2027",
        "description": "Tableros ejecutivos y autoservicio analítico para las vicepresidencias comerciales y de operaciones.",
        "job_ids": [4634, 637, 2822, 4428],
    },
    {
        "code": "PRJ-06", "name": "Migración Cloud Híbrida", "area": "Infraestructura", "status": "Planificación",
        "start": "Nov 2026", "end": "Jun 2027",
        "description": "Traslado de cargas críticas a una arquitectura híbrida con alta disponibilidad y seguridad por diseño.",
        "job_ids": [7178, 7131, 2212, 7887],
    },
    {
        "code": "PRJ-07", "name": "Asistente Virtual Cognitivo", "area": "IA Conversacional", "status": "Próximo",
        "start": "Ene 2027", "end": "Ago 2027",
        "description": "Asistente de lenguaje natural para atención al cliente y soporte interno con supervisión humana.",
        "job_ids": [3991, 4002, 3677, 2674],
    },
    {
        "code": "PRJ-08", "name": "Transformación Digital ERP", "area": "Consultoría TI", "status": "Planificación",
        "start": "Dic 2026", "end": "Oct 2027",
        "description": "Modernización de procesos financieros y operativos con integración de sistemas y gestión del cambio.",
        "job_ids": [6806, 2628, 6283, 8097],
    },
]
