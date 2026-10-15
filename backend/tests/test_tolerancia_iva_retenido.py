"""Tolerancia de ±$1.00 SOLO en el IVA retenido (acuerdo de reunión oct 2026):
los sistemas de algunos profesores calculan la retención con otra tasa o
redondeo. El resto de los campos conserva la tolerancia estricta (±$0.10)."""
from decimal import Decimal

from app.services.validador import validar_cfdi
from tests.factories import add_clave, add_montos, add_profesor, build_cfdi


def _errores(detalles):
    return [d["campo"] for d in detalles if not d["resultado"]]


def _setup_con_iva_ret_desviado(db, delta: str):
    """Layout con montos correctos; CFDI con el IVA retenido desviado `delta`
    pesos (el total del CFDI se recalcula con su propio IVA retenido, como lo
    haría el sistema del profesor)."""
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    base = build_cfdi(regimen="612", rfc_emisor=prof.rfc)
    add_montos(db, prof, base)
    iva_ret = base.iva_retenido + Decimal(delta)
    return build_cfdi(regimen="612", rfc_emisor=prof.rfc,
                      iva_retenido=str(iva_ret), uuid="TEST-UUID-TOL1")


def test_iva_retenido_desviado_50_centavos_aprueba(db):
    cfdi = _setup_con_iva_ret_desviado(db, "0.50")
    detalles, estado, _ = validar_cfdi(cfdi, db)
    assert estado == "aprobada", _errores(detalles)


def test_iva_retenido_desviado_exactamente_1_peso_aprueba(db):
    cfdi = _setup_con_iva_ret_desviado(db, "-1.00")
    detalles, estado, _ = validar_cfdi(cfdi, db)
    assert estado == "aprobada", _errores(detalles)


def test_iva_retenido_desviado_mas_de_1_peso_rechaza(db):
    cfdi = _setup_con_iva_ret_desviado(db, "1.50")
    detalles, estado, _ = validar_cfdi(cfdi, db)
    assert estado == "rechazada"
    # Solo caen los campos de IVA retenido (y el total del layout, que arrastra
    # la misma diferencia); nada más se ve afectado.
    assert set(_errores(detalles)) == {"IVA Retenido", "IVA Retenido (layout)", "Total (layout)"}


def test_isr_conserva_tolerancia_estricta(db):
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    base = build_cfdi(regimen="612", rfc_emisor=prof.rfc)
    add_montos(db, prof, base)
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc,
                      isr_retenido=str(base.isr_retenido + Decimal("0.50")),
                      uuid="TEST-UUID-TOL2")
    detalles, estado, _ = validar_cfdi(cfdi, db)
    assert estado == "rechazada"
    assert "ISR retenido" in _errores(detalles)


def test_total_sin_desviacion_de_iva_sigue_estricto(db):
    """Si el IVA retenido coincide, el total NO gana margen extra: una
    diferencia de $0.50 en el total sigue rechazándose."""
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    base = build_cfdi(regimen="612", rfc_emisor=prof.rfc)
    add_montos(db, prof, base)
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc,
                      total=str(base.total + Decimal("0.50")),
                      uuid="TEST-UUID-TOL3")
    detalles, estado, _ = validar_cfdi(cfdi, db)
    assert estado == "rechazada"
    assert "Total (layout)" in _errores(detalles)
