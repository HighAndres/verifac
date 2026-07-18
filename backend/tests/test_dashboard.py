"""Pruebas del resumen mensual (dashboard)."""
from datetime import datetime, timezone
from decimal import Decimal

from app.models.factura import Factura
from app.services.dashboard import resumen_mes
from tests.factories import add_montos, add_profesor, build_cfdi


def _factura(db, cfdi, estado):
    f = Factura(
        uuid_cfdi=cfdi.uuid, rfc_emisor=cfdi.rfc_emisor, nombre_emisor=cfdi.nombre_emisor,
        regimen_emisor=cfdi.regimen_fiscal, fecha_emision=cfdi.fecha,
        subtotal=cfdi.subtotal, total=cfdi.total, estado=estado,
        origen="xml", pdf_cotejo="sin_pdf", fecha_validacion=datetime.now(timezone.utc),
    )
    db.add(f)
    db.flush()
    return f


def test_resumen_mes_vacio(db):
    r = resumen_mes(db, 1, 2099)
    assert r["facturas"]["total"] == 0
    assert r["montos"]["esperado_total"] == 0
    assert r["pendientes_envio"] == []


def test_resumen_cuenta_estados_y_montos(db):
    p1 = add_profesor(db, rfc="AAA010101AA1", nombre="PROFE UNO", regimen="612")
    p2 = add_profesor(db, rfc="BBB010101BB2", nombre="PROFE DOS", regimen="612")
    c1 = build_cfdi(rfc_emisor=p1.rfc, fecha=datetime(2099, 1, 10), uuid="DASH-1")
    c2 = build_cfdi(rfc_emisor=p2.rfc, fecha=datetime(2099, 1, 12), uuid="DASH-2")
    add_montos(db, p1, c1)
    add_montos(db, p2, c2)
    _factura(db, c1, "aprobada")
    _factura(db, c2, "rechazada")

    r = resumen_mes(db, 1, 2099)
    assert r["facturas"] == {"total": 2, "aprobadas": 1, "rechazadas": 1, "otras": 0}
    assert r["montos"]["profesores_en_layout"] == 2
    assert r["montos"]["aprobado_total"] == float(c1.total)
    assert r["montos"]["esperado_total"] == float(c1.total + c2.total)
    # p2 tiene layout pero su factura fue rechazada -> sigue pendiente
    assert [p["rfc"] for p in r["pendientes_envio"]] == [p2.rfc]


def test_resumen_ignora_otros_meses(db):
    p = add_profesor(db, rfc="CCC010101CC3", nombre="PROFE TRES", regimen="612")
    c_ene = build_cfdi(rfc_emisor=p.rfc, fecha=datetime(2099, 1, 10), uuid="DASH-3")
    _factura(db, c_ene, "aprobada")

    r = resumen_mes(db, 2, 2099)   # febrero: no debe ver la factura de enero
    assert r["facturas"]["total"] == 0
