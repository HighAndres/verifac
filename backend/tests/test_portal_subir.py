"""Pruebas del registro de factura subida por el profesor desde el portal."""
import pytest

from app.services.factura_portal import (
    FacturaAjena, FacturaDuplicada, registrar_factura_portal,
)
from tests.factories import add_clave, add_montos, add_profesor, build_cfdi, build_pdf


def test_sube_propia_aprobada_con_pdf_ok(db):
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc, uuid="PORTAL-OK-1")
    add_montos(db, prof, cfdi)
    pdf = build_pdf(cfdi.uuid)   # el PDF contiene el UUID → cotejo ok

    factura = registrar_factura_portal(cfdi, pdf, prof, db)
    assert factura.estado == "aprobada"
    assert factura.origen == "portal"
    assert factura.pdf_cotejo == "ok"


def test_no_puede_subir_ajena(db):
    prof = add_profesor(db, rfc="AAAA010101AAA", regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_emisor="BBBB020202BBB", uuid="PORTAL-AJENA-1")
    with pytest.raises(FacturaAjena):
        registrar_factura_portal(cfdi, build_pdf(cfdi.uuid), prof, db)


def test_pdf_no_coincide_rechaza(db):
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc, uuid="PORTAL-PDFBAD-1")
    add_montos(db, prof, cfdi)
    pdf = build_pdf("otro folio distinto")   # no contiene el UUID

    factura = registrar_factura_portal(cfdi, pdf, prof, db)
    assert factura.estado == "rechazada"
    assert factura.pdf_cotejo == "no_coincide"


def test_uuid_duplicado(db):
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc, uuid="PORTAL-DUP-1")
    add_montos(db, prof, cfdi)
    registrar_factura_portal(cfdi, build_pdf(cfdi.uuid), prof, db)

    with pytest.raises(FacturaDuplicada):
        registrar_factura_portal(cfdi, build_pdf(cfdi.uuid), prof, db)
