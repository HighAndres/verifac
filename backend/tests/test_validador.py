"""Pruebas del motor de validación fiscal y la conciliación contra el layout."""
from datetime import datetime
from decimal import Decimal

from app.services.validador import validar_cfdi
from tests.factories import add_clave, add_montos, add_profesor, build_cfdi


def _errores(detalles):
    return [d["campo"] for d in detalles if not d["resultado"]]


def test_612_valida_y_concilia(db):
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc)
    add_montos(db, prof, cfdi)
    detalles, estado, motivo = validar_cfdi(cfdi, db)
    assert estado == "aprobada", _errores(detalles)
    assert motivo is None


def test_626_resico_retenciones(db):
    add_clave(db)
    prof = add_profesor(db, rfc="ROSA010101AAA", regimen="626")
    cfdi = build_cfdi(regimen="626", rfc_emisor=prof.rfc)  # ISR 1.25%
    add_montos(db, prof, cfdi)
    detalles, estado, _ = validar_cfdi(cfdi, db)
    assert estado == "aprobada", _errores(detalles)


def test_603_sin_retenciones(db):
    add_clave(db)
    prof = add_profesor(db, rfc="ADT010101AAA", regimen="603")
    cfdi = build_cfdi(regimen="603", rfc_emisor=prof.rfc)  # IVA=0, sin retenciones
    add_montos(db, prof, cfdi)
    detalles, estado, _ = validar_cfdi(cfdi, db)
    assert estado == "aprobada", _errores(detalles)


def test_isr_incorrecto_rechaza(db):
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    # ISR de 5% en vez de 10% para régimen 612
    cfdi = build_cfdi(regimen="612", isr_retenido="50.00")
    add_montos(db, prof, cfdi)
    detalles, estado, _ = validar_cfdi(cfdi, db)
    assert estado == "rechazada"
    assert "ISR retenido" in _errores(detalles)


def test_total_alterado_rechaza(db):
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", total="9999.99")
    add_montos(db, prof, cfdi)
    detalles, estado, _ = validar_cfdi(cfdi, db)
    assert estado == "rechazada"
    assert "Total" in _errores(detalles)


def test_receptor_incorrecto_rechaza(db):
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_receptor="XXXX999999XXX")
    add_montos(db, prof, cfdi)
    detalles, estado, _ = validar_cfdi(cfdi, db)
    assert estado == "rechazada"
    assert "Nombre receptor" in _errores(detalles)


def test_regimen_no_coincide_con_profesor(db):
    add_clave(db)
    add_profesor(db, regimen="612")           # perfil dice 612
    cfdi = build_cfdi(regimen="626")          # XML dice 626
    detalles, estado, _ = validar_cfdi(cfdi, db)
    assert estado == "rechazada"
    assert "Clave régimen emisor" in _errores(detalles)


def test_sin_layout_rechaza_no_aprueba_en_silencio(db):
    """Candado clave: sin layout del mes, la factura NO puede aprobarse."""
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc)  # sin add_montos
    detalles, estado, _ = validar_cfdi(cfdi, db)
    assert estado == "rechazada"
    assert "Conciliación (layout)" in _errores(detalles)


def test_mes_equivocado_rechaza(db):
    """Layout de junio, XML de mayo -> no encuentra layout -> rechaza."""
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi_jun = build_cfdi(regimen="612", rfc_emisor=prof.rfc, fecha=datetime(2026, 6, 15))
    add_montos(db, prof, cfdi_jun)            # solo junio
    cfdi_may = build_cfdi(regimen="612", rfc_emisor=prof.rfc, fecha=datetime(2026, 5, 15))
    detalles, estado, _ = validar_cfdi(cfdi_may, db)
    assert estado == "rechazada"
    assert "Conciliación (layout)" in _errores(detalles)


def test_montos_no_cuadran_con_layout_rechaza(db):
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc, subtotal="1000.00")
    # Layout con subtotal distinto al del XML
    otro = build_cfdi(regimen="612", rfc_emisor=prof.rfc, subtotal="2000.00")
    add_montos(db, prof, otro)
    detalles, estado, _ = validar_cfdi(cfdi, db)
    assert estado == "rechazada"
    assert "Subtotal (layout)" in _errores(detalles)
