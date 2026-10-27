"""Lectura de documentos: PDF con texto, PDF escaneado (OCR) e imágenes.

El archivo original se procesa en memoria y NO se guarda en disco (minimización);
sólo se conserva su huella SHA-256 para evitar duplicados.
"""
from __future__ import annotations

import io
import logging
import threading
from dataclasses import dataclass, field
from functools import lru_cache

log = logging.getLogger("talentmatch.reader")
_PDFIUM_LOCK = threading.Lock()  # pdfium no es thread-safe


@dataclass
class ReadResult:
    text: str
    source_type: str               # pdf-texto | pdf-escaneado | imagen
    method: str
    pages: int = 1
    ocr_used: bool = False
    photo_detected: bool = False
    warnings: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def _ocr_lang() -> str:
    try:
        import pytesseract

        langs = set(pytesseract.get_languages(config=""))
        if {"spa", "eng"} <= langs:
            return "spa+eng"
        if "spa" in langs:
            return "spa"
        return "eng"
    except Exception:  # pragma: no cover - depende del sistema
        return "eng"


def ocr_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_image(img) -> str:
    import pytesseract
    from PIL import ImageOps

    img = ImageOps.exif_transpose(img).convert("L")
    if img.width > 2600:
        ratio = 2600 / img.width
        img = img.resize((2600, int(img.height * ratio)))
    if img.width < 1400:
        ratio = 1400 / img.width
        img = img.resize((int(img.width * ratio), int(img.height * ratio)))
    img = ImageOps.autocontrast(img)
    return pytesseract.image_to_string(img, lang=_ocr_lang(), config="--psm 4")


def read_pdf(data: bytes) -> ReadResult:
    import pdfplumber

    texts: list[str] = []
    photo = False
    pages = 0
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = len(pdf.pages)
        for page in pdf.pages:
            texts.append(page.extract_text(x_tolerance=1.5, y_tolerance=3) or "")
            for im in page.images or []:
                w = float(im.get("width", 0))
                h = float(im.get("height", 0))
                # Imagen pequeña y vertical en la primera página ≈ foto de perfil
                if page.page_number == 1 and 40 < w < page.width * 0.45 and h > w * 0.9:
                    photo = True
    text = "\n".join(texts).strip()
    chars_per_page = len(text.replace(" ", "")) / max(pages, 1)
    if chars_per_page >= 120:
        return ReadResult(text=text, source_type="pdf-texto", method="Extracción de texto embebido (pdfplumber)",
                          pages=pages, photo_detected=photo)

    # PDF escaneado → OCR página a página
    if not ocr_available():
        return ReadResult(text=text, source_type="pdf-escaneado", method="Sin OCR disponible", pages=pages,
                          warnings=["El PDF parece escaneado y el motor OCR (Tesseract) no está instalado."])
    import pypdfium2 as pdfium

    ocr_texts = []
    with _PDFIUM_LOCK:
        pdf = pdfium.PdfDocument(data)
        try:
            n = min(len(pdf), 4)
            for i in range(n):
                page = pdf[i]
                img = page.render(scale=250 / 72, grayscale=True).to_pil()
                page.close()
                ocr_texts.append(_ocr_image(img))   # una página a la vez: menor pico de memoria
                del img
        finally:
            pdf.close()
    return ReadResult(text="\n".join(ocr_texts).strip(), source_type="pdf-escaneado",
                      method=f"OCR Tesseract ({_ocr_lang()}) sobre páginas rasterizadas a 250 dpi",
                      pages=pages, ocr_used=True, photo_detected=False,
                      warnings=[] if ocr_texts else ["No se pudo leer texto del PDF escaneado."])


def read_image(data: bytes) -> ReadResult:
    from PIL import Image

    if not ocr_available():
        return ReadResult(text="", source_type="imagen", method="Sin OCR disponible",
                          warnings=["El motor OCR (Tesseract) no está instalado."])
    img = Image.open(io.BytesIO(data))
    if img.width * img.height > 40_000_000:
        return ReadResult(text="", source_type="imagen", method="Imagen demasiado grande",
                          warnings=["La imagen supera 40 megapíxeles; redúzcala o use PDF."])
    return ReadResult(text=_ocr_image(img), source_type="imagen", method=f"OCR Tesseract ({_ocr_lang()})", ocr_used=True)
