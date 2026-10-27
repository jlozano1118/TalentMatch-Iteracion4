"""Imprime las métricas de evaluación de la extracción (precisión, exhaustividad, línea base).

Uso:  python -m scripts.evaluate
"""
import json

from app.business.evaluation_service import extraction_benchmark

if __name__ == "__main__":
    print(json.dumps(extraction_benchmark(), ensure_ascii=False, indent=2))
