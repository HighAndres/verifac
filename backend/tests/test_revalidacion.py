"""Pruebas de la revalidación de facturas (candado #4)."""
from datetime import datetime, timezone

from app.models.factura import Factura
from app.services.revalidacion import revalidar_factura
from tests.factories import add_clave, add_montos, add_profesor, build_cfdi


def _factura_desde_cfdi(db, cfdi, estado="rechazada") -> Factura:
    f = Factura(
        uuid_cfdi=cfdi.uuid, rfc_emisor=cfdi.rfc_emisor, nombre_emisor=cfdi.nombre_emisor,
        regimen_emisor=cfdi.regimen_fiscal, rfc_receptor=cfdi.rfc_receptor,
        nombre_receptor=cfdi.nombre_receptor, moneda=cfdi.moneda, fecha_emision=cfdi.fecha,
        subtotal=cfdi.subtotal, iva_trasladado=cfdi.iva_trasladado, iva_retenido=cfdi.iva_retenido,
        isr_retenido=cfdi.isr_retenido, total=cfdi.total,
        clave_servicio=cfdi.conceptos[0].clave_prod_serv, clave_unidad=cfdi.conceptos[0].clave_unidad,
        forma_pago=cfdi.forma_pago, metodo_pago=cfdi.metodo_pago, uso_cfdi=cfdi.uso_cfdi,
        estado=estado, origen="xml", pdf_cotejo="sin_pdf",
        fecha_validacion=datetime.now(timezone.utc),
    )
    db.add(f)
    db.flush()
    return f


def test_revalidar_aprueba_cuando_ya_hay_layout(db):
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc, uuid="TEST-REVAL-1")
    add_montos(db, prof, cfdi)                       # el layout ya existe
    factura = _factura_desde_cfdi(db, cfdi, estado="rechazada")
    estado, motivo = revalidar_factura(factura, db)
    assert estado == "aprobada", motivo
    assert factura.estado == "aprobada"


def test_revalidar_mantiene_rechazo_sin_layout(db):
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc, uuid="TEST-REVAL-2")
    factura = _factura_desde_cfdi(db, cfdi, estado="rechazada")  # sin montos
    estado, _ = revalidar_factura(factura, db)
    assert estado == "rechazada"


def test_revalidar_respeta_veredicto_pdf(db):
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc, uuid="TEST-REVAL-3")
    add_montos(db, prof, cfdi)
    factura = _factura_desde_cfdi(db, cfdi, estado="rechazada")
    factura.pdf_cotejo = "no_coincide"              # el PDF no correspondía
    estado, _ = revalidar_factura(factura, db)
    assert estado == "rechazada"                    # no aprueba aunque lo fiscal cuadre
