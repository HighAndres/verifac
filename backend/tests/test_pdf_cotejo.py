"""Pruebas del cotejo PDF↔XML (candado #6)."""
from app.services.pdf_cotejo import cotejar_pdf
from tests.factories import build_pdf

UUID = "A1B2C3D4-E5F6-7890-ABCD-1234567890EF"


def test_sin_pdf():
    assert cotejar_pdf(UUID, []) == "sin_pdf"


def test_pdf_contiene_uuid_ok():
    pdf = build_pdf("Folio Fiscal " + UUID)
    assert cotejar_pdf(UUID, [pdf]) == "ok"


def test_pdf_no_contiene_uuid():
    pdf = build_pdf("Folio Fiscal 00000000-0000-0000-0000-000000000000")
    assert cotejar_pdf(UUID, [pdf]) == "no_coincide"


def test_pdf_ilegible():
    assert cotejar_pdf(UUID, [b"esto no es un pdf"]) == "ilegible"


def test_ok_entre_varios_pdfs():
    malo = build_pdf("otro documento")
    bueno = build_pdf(UUID)
    assert cotejar_pdf(UUID, [malo, bueno]) == "ok"
