"""
Cotejo del PDF adjunto contra el XML del CFDI (candado #6).

No usa servicios externos: extrae el texto del PDF localmente con pypdf y verifica
que contenga el UUID (Folio Fiscal) del XML. Resultados posibles:
  - "ok"          → el UUID del XML aparece en algún PDF adjunto.
  - "no_coincide" → se pudo leer texto del PDF pero el UUID no aparece.
  - "ilegible"    → hay PDF pero no se pudo extraer texto (p. ej. escaneado).
  - "sin_pdf"     → no llegó ningún PDF junto al XML.
Solo "no_coincide" debe reprobar la factura; el resto es informativo.
"""
import io
import logging
import re

logger = logging.getLogger(__name__)


def extraer_texto_pdf(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # PDF corrupto, cifrado, etc.
        logger.warning("No se pudo leer el PDF: %s", exc)
        return ""


def _sin_espacios(texto: str) -> str:
    return re.sub(r"\s+", "", texto).upper()


def cotejar_pdf(uuid: str, pdfs: list[bytes]) -> str:
    """Devuelve el resultado del cotejo del UUID contra los PDFs adjuntos."""
    if not pdfs:
        return "sin_pdf"
    if not uuid:
        return "no_coincide"

    objetivo = _sin_espacios(uuid)
    hubo_texto = False
    for pdf in pdfs:
        texto = extraer_texto_pdf(pdf)
        if texto.strip():
            hubo_texto = True
            if objetivo in _sin_espacios(texto):
                return "ok"
    return "no_coincide" if hubo_texto else "ilegible"
