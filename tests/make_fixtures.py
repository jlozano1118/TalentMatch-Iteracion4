"""Genera CV de PRUEBA (ficticios, sólo para pruebas automáticas) en PDF texto, PDF escaneado,
imagen y JSON. No forman parte de los datos de la aplicación.

Uso:  python -m tests.make_fixtures
"""
from __future__ import annotations

import io
import json
from pathlib import Path

OUT = Path(__file__).parent / "fixtures"

CV_DATA_ENGINEER = """LAURA PATRICIA MENDOZA RUIZ
Ingeniera de Datos | Analítica y Big Data
laura.mendoza.test@example.com | +57 310 555 0101 | Bogotá, Colombia
Fecha de nacimiento: 12/03/1994
Estado civil: Soltera
C.C. 1.020.555.555

PERFIL PROFESIONAL
Ingeniera de sistemas con 5 años de experiencia construyendo pipelines de datos y modelos analíticos.
Orientada a resultados, con pensamiento crítico y comunicación asertiva con áreas de negocio.

EXPERIENCIA LABORAL
Data Engineer - Banco Andino S.A.  Ene 2022 - Actualidad
Diseñé pipelines ETL con Apache Airflow y Spark sobre AWS (S3, Redshift). Lideré un equipo de 4 personas.
Modelado de datos en PostgreSQL y SQL Server; tableros en Power BI para la vicepresidencia comercial.
Analista de Datos - Retail Express  Mar 2019 - Dic 2021
Análisis de datos con Python (pandas, NumPy) y SQL. Capacité a 20 usuarios en visualización de datos.

FORMACIÓN ACADÉMICA
Ingeniería de Sistemas - Universidad Nacional de Colombia (2013 - 2018)
Especialización en Analítica de Datos - Universidad de los Andes (2020)

HABILIDADES TÉCNICAS
Python, SQL, Apache Spark, Apache Kafka, Airflow, AWS, Docker, Git, Power BI, Tableau, Machine Learning, Data Warehousing

HABILIDADES BLANDAS
Trabajo en equipo, Liderazgo, Resolución de problemas, Comunicación, Adaptabilidad

IDIOMAS
Inglés B2, Español nativo

CERTIFICACIONES
AWS Certified Cloud Practitioner (2023)

REFERENCIAS
Carlos Pérez - Gerente - 300 000 0000
"""

CV_FULLSTACK = """JUAN DAVID CASTRO LÓPEZ
Desarrollador Full Stack
juan.castro.test@example.com  +57 320 555 0202  Medellín, Colombia

RESUMEN
Desarrollador con 3 años de experiencia en aplicaciones web con React, Node.js y Java Spring Boot.

EXPERIENCIA
Desarrollador Full Stack - Fintech Nova  Jun 2023 - Presente
APIs REST con Node.js y Express, frontend en React y TypeScript, despliegue con Docker y Jenkins (CI/CD).
Desarrollador Junior - Software Andes  Feb 2021 - May 2023
Microservicios con Java y Spring Boot, bases de datos MySQL y MongoDB. Pruebas unitarias con Jest.

EDUCACIÓN
Tecnólogo en Análisis y Desarrollo de Software - SENA (2020)
Ingeniería de Software (en curso, 8vo semestre) - Universidad EAFIT

SKILLS
JavaScript, TypeScript, React, Node.js, Java, Spring Boot, HTML, CSS, MySQL, MongoDB, Git, Docker, AWS

HABILIDADES BLANDAS
Aprendizaje continuo, trabajo en equipo, creatividad, gestión del tiempo

IDIOMAS
Inglés intermedio
"""

CV_JSON_RESUME = {
    "basics": {
        "name": "Mariana Torres Gil", "label": "Científica de Datos", "email": "mariana.torres.test@example.com",
        "phone": "+57 301 555 0303", "summary": "Científica de datos enfocada en modelos de riesgo y NLP.",
        "location": {"city": "Cali", "countryCode": "CO"},
    },
    "fecha_nacimiento": "1996-07-21",
    "genero": "F",
    "work": [
        {"name": "Aseguradora del Pacífico", "position": "Data Scientist", "startDate": "2021-02", "endDate": "",
         "summary": "Modelos de machine learning con scikit-learn y XGBoost para scoring de riesgo; NLP con spaCy.",
         "highlights": ["Lideré la migración de modelos a AWS SageMaker", "Presenté resultados a la junta directiva"]},
        {"name": "Universidad del Valle", "position": "Asistente de investigación", "startDate": "2019-01", "endDate": "2020-12",
         "summary": "Análisis estadístico en R y Python."},
    ],
    "education": [{"institution": "Universidad del Valle", "area": "Estadística", "studyType": "Pregrado"},
                  {"institution": "Universidad Icesi", "area": "Ciencia de Datos", "studyType": "Maestría"}],
    "skills": [{"name": "Machine Learning", "keywords": ["Python", "scikit-learn", "TensorFlow", "XGBoost"]},
               {"name": "Datos", "keywords": ["SQL", "Pandas", "Statistics", "R", "Tableau"]}],
    "soft_skills": ["Pensamiento crítico", "Comunicación", "Mentoría"],
    "languages": [{"language": "Inglés", "fluency": "C1"}],
}

CV_JSON_ATS_ES = {
    "candidato": {"nombre": "Andrés Felipe Rincón", "correo": "andres.rincon.test@example.com", "telefono": "3155550404",
                  "cargo_actual": "Administrador de Infraestructura", "ciudad": "Bogotá"},
    "cedula": "1010555555",
    "experiencia": [
        {"cargo": "Administrador de Sistemas", "empresa": "Telecom Andina", "fecha_inicio": "2018-05", "fecha_fin": "actual",
         "descripcion": "Administración de servidores Linux y Windows Server, Active Directory, VMware y redes TCP/IP."},
    ],
    "educacion": [{"titulo": "Ingeniería Electrónica", "institucion": "Universidad Distrital", "nivel": "Profesional"}],
    "habilidades_tecnicas": ["Linux", "Windows Server", "Active Directory", "Virtualization", "Networking", "Bash", "Ansible", "Troubleshooting"],
    "power_skills": ["Orientación al cliente", "Toma de decisiones", "Trabajo bajo presión"],
    "idiomas": ["Inglés B1"],
}


def _pdf_from_text(text: str) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in text.splitlines():
        c.setFont("Helvetica-Bold" if line.isupper() and line.strip() else "Helvetica", 10)
        c.drawString(50, y, line)
        y -= 15
        if y < 50:
            c.showPage()
            y = 750
    c.save()
    return buf.getvalue()


def _image_from_text(text: str):
    from PIL import Image, ImageDraw, ImageFont

    lines = text.splitlines()
    img = Image.new("RGB", (1700, 60 + 34 * len(lines)), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
    for i, line in enumerate(lines):
        d.text((60, 30 + 34 * i), line, fill="black", font=font)
    return img


def main() -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / "cv_texto_data_engineer.pdf").write_bytes(_pdf_from_text(CV_DATA_ENGINEER))
    img = _image_from_text(CV_FULLSTACK)
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=200)
    (OUT / "cv_escaneado_fullstack.pdf").write_bytes(buf.getvalue())
    img.save(OUT / "cv_imagen_fullstack.png")
    (OUT / "cv_json_resume.json").write_text(json.dumps(CV_JSON_RESUME, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "cv_json_ats_es.json").write_text(json.dumps(CV_JSON_ATS_ES, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Fixtures generados en", OUT)


if __name__ == "__main__":
    main()
