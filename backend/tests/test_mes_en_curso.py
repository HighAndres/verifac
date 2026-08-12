"""Regla: solo se aceptan facturas emitidas en el mes en curso (al recibirlas).

Una factura de un mes anterior se rechaza aunque exista layout de ese mes y los
montos coincidan (caso real: profesor subió por el portal una factura de junio en
agosto y quedó aprobada). La revalidación evalúa contra el created_at de la
factura, no contra hoy, para no tumbar facturas que llegaron a tiempo.
"""
from datetime import datetime, timedelta

from app.services.factura_portal import registrar_factura_portal
from app.services.revalidacion import revalidar_factura
from app.services.validador import validar_cfdi
from tests.factories import add_clave, add_montos, add_profesor, build_cfdi, build_pdf, fecha_mes_actual


def _mes_anterior(dia: int = 15) -> datetime:
    primero = fecha_mes_actual(1)
    previo = primero - timedelta(days=1)
    return datetime(previo.year, previo.month, dia)


def _errores(detalles):
    return [d["campo"] for d in detalles if not d["resultado"]]


def test_factura_de_mes_anterior_rechazada_aunque_haya_layout(db):
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc, fecha=_mes_anterior())
    add_montos(db, prof, cfdi)  # layout del mes anterior existe y los montos cuadran

    detalles, estado, motivo = validar_cfdi(cfdi, db)
    assert estado == "rechazada"
    assert "Mes de emisión" in _errores(detalles)
    assert "Mes de emisión" in (motivo or "")


def test_factura_del_mes_en_curso_pasa_la_regla(db):
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc)  # default: mes en curso
    add_montos(db, prof, cfdi)

    detalles, estado, _ = validar_cfdi(cfdi, db)
    assert estado == "aprobada"
    assert "Mes de emisión" not in _errores(detalles)


def test_portal_rechaza_factura_de_mes_anterior(db):
    """El flujo completo del portal registra la factura pero rechazada."""
    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc,
                      fecha=_mes_anterior(), uuid="PORTAL-VIEJA-1")
    add_montos(db, prof, cfdi)

    factura = registrar_factura_portal(cfdi, build_pdf(cfdi.uuid), prof, db)
    assert factura.estado == "rechazada"
    assert "Mes de emisión" in (factura.motivo_rechazo or "")


def test_revalidar_respeta_mes_de_recepcion(db):
    """Factura emitida y recibida el mes pasado (rechazada entonces por falta de
    layout): al revalidarla hoy, la regla del mes se evalúa contra su created_at,
    así que puede aprobarse."""
    from datetime import timezone

    from app.models.factura import Factura

    add_clave(db)
    prof = add_profesor(db, regimen="612")
    cfdi = build_cfdi(regimen="612", rfc_emisor=prof.rfc,
                      fecha=_mes_anterior(), uuid="REVAL-MES-1")
    add_montos(db, prof, cfdi)  # el layout ya está cargado al revalidar

    f = Factura(
        uuid_cfdi=cfdi.uuid, rfc_emisor=cfdi.rfc_emisor, nombre_emisor=cfdi.nombre_emisor,
        regimen_emisor=cfdi.regimen_fiscal, rfc_receptor=cfdi.rfc_receptor,
        nombre_receptor=cfdi.nombre_receptor, moneda=cfdi.moneda, fecha_emision=cfdi.fecha,
        subtotal=cfdi.subtotal, iva_trasladado=cfdi.iva_trasladado,
        iva_retenido=cfdi.iva_retenido, isr_retenido=cfdi.isr_retenido, total=cfdi.total,
        clave_servicio=cfdi.conceptos[0].clave_prod_serv, clave_unidad=cfdi.conceptos[0].clave_unidad,
        forma_pago=cfdi.forma_pago, metodo_pago=cfdi.metodo_pago, uso_cfdi=cfdi.uso_cfdi,
        estado="rechazada", origen="portal",
        created_at=cfdi.fecha.replace(tzinfo=timezone.utc),  # recibida en su propio mes
    )
    db.add(f)
    db.flush()

    estado, motivo = revalidar_factura(f, db)
    assert estado == "aprobada", motivo
