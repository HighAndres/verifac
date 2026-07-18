"""Builders para las pruebas: CFDIData sintético, registros de BD y PDFs mínimos."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.core.config import settings
from app.models.catalogo_clave import CatalogoClave
from app.models.monto_mensual import MontoMensual
from app.models.profesor import Profesor
from app.services.cfdi_parser import CFDIData, ConceptoCFDI

Q = Decimal("0.01")


def build_cfdi(
    *,
    regimen: str = "612",
    subtotal: str = "1000.00",
    fecha: datetime = datetime(2026, 6, 15),
    rfc_emisor: str = "XAXX010101000",
    nombre_emisor: str = "TEST EMISOR",
    rfc_receptor: Optional[str] = None,
    clave_serv: str = "90141702",
    clave_unidad: str = "E48",
    total: Optional[str] = None,
    iva_trasladado: Optional[str] = None,
    iva_retenido: Optional[str] = None,
    isr_retenido: Optional[str] = None,
    forma_pago: str = "03",
    metodo_pago: str = "PUE",
    uso_cfdi: str = "G03",
    moneda: str = "MXN",
    uuid: str = "TEST-UUID-0001",
) -> CFDIData:
    sub = Decimal(subtotal)
    if regimen == "603":
        ivaT, ivaR, isr = Decimal("0"), Decimal("0"), Decimal("0")
        objeto = "01"
    else:
        ivaT = Decimal(iva_trasladado) if iva_trasladado is not None else (sub * Decimal("0.16")).quantize(Q)
        ivaR = Decimal(iva_retenido) if iva_retenido is not None else (sub * Decimal("0.16") * 2 / 3).quantize(Q)
        rate = Decimal("0.0125") if regimen == "626" else Decimal("0.10")
        isr = Decimal(isr_retenido) if isr_retenido is not None else (sub * rate).quantize(Q)
        objeto = "02"
    tot = Decimal(total) if total is not None else (sub + ivaT - ivaR - isr).quantize(Q)
    return CFDIData(
        fecha=fecha, subtotal=sub, total=tot, forma_pago=forma_pago, metodo_pago=metodo_pago,
        rfc_emisor=rfc_emisor, nombre_emisor=nombre_emisor, regimen_fiscal=regimen,
        rfc_receptor=rfc_receptor or settings.RFC_RECEPTOR, nombre_receptor=settings.NOMBRE_RECEPTOR,
        uso_cfdi=uso_cfdi, moneda=moneda,
        conceptos=[ConceptoCFDI(clave_serv, clave_unidad, "Servicio profesional", sub, objeto)],
        iva_trasladado=ivaT, iva_retenido=ivaR, isr_retenido=isr, uuid=uuid,
    )


def add_profesor(db, rfc="XAXX010101000", nombre="TEST EMISOR", regimen="612") -> Profesor:
    p = Profesor(rfc=rfc, nombre=nombre, correo="test@example.com", regimen_fiscal=regimen, activo=True)
    db.add(p)
    db.flush()
    return p


def add_clave(db, clave="90141702") -> CatalogoClave:
    existente = db.query(CatalogoClave).filter(CatalogoClave.clave == clave).first()
    if existente:
        return existente
    c = CatalogoClave(clave=clave, descripcion="Servicio", tipo="servicio", activo=True)
    db.add(c)
    db.flush()
    return c


def add_montos(db, profesor, cfdi, mes=None, anio=None) -> MontoMensual:
    m = MontoMensual(
        profesor_id=profesor.id, nombre_layout=profesor.nombre, rfc_emisor=profesor.rfc,
        regimen_fiscal=profesor.regimen_fiscal, mes=mes or cfdi.fecha.month, anio=anio or cfdi.fecha.year,
        subtotal=cfdi.subtotal, iva_trasladado=cfdi.iva_trasladado, iva_retenido=cfdi.iva_retenido,
        isr_retenido=cfdi.isr_retenido, total=cfdi.total,
    )
    db.add(m)
    db.flush()
    return m


def build_pdf(texto: str) -> bytes:
    """PDF 1.4 mínimo con una línea de texto (xref válido para que pypdf lo lea)."""
    stream = b"BT /F1 12 Tf 20 100 Td (" + texto.encode("latin-1") + b") Tj ET"
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 400 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length %d>>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj" % i + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref_pos)
    return out
