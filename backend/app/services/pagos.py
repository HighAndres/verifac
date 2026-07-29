"""Vista mensual de pagos a profesores.

Arma, para un mes/año, una fila por profesor activo combinando en memoria
(patrón de `services/dashboard.resumen_mes`):
- datos del profesor,
- contexto de su factura del mes (estado + total) y monto esperado del layout,
- estado del pago registrado (tabla `pagos`), si existe.
"""
from datetime import datetime, timezone

from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.models.factura import Factura
from app.models.monto_mensual import MontoMensual
from app.models.pago import Pago
from app.models.profesor import Profesor

# Prioridad al elegir "la" factura del mes de un profesor (mayor = preferida).
_PRIORIDAD_ESTADO = {"aprobada": 3, "pendiente": 2, "rechazada": 1}


def _fmt(v) -> float | None:
    return float(v) if v is not None else None


def lista_mensual(db: Session, mes: int, anio: int) -> list[dict]:
    # Se listan TODOS los profesores del catálogo (activos e inactivos), igual que
    # la pantalla de Profesores, para no ocultar a nadie silenciosamente.
    profesores = (
        db.query(Profesor)
        .order_by(Profesor.nombre)
        .all()
    )

    # Facturas del mes → mejor factura por RFC (aprobada > pendiente > rechazada; luego reciente).
    facturas = (
        db.query(Factura)
        .filter(
            extract("month", Factura.fecha_emision) == mes,
            extract("year", Factura.fecha_emision) == anio,
        )
        .all()
    )
    mejor_por_rfc: dict[str, Factura] = {}
    for f in facturas:
        actual = mejor_por_rfc.get(f.rfc_emisor)
        if actual is None or _es_mejor(f, actual):
            mejor_por_rfc[f.rfc_emisor] = f

    # Monto esperado del layout por profesor.
    montos = (
        db.query(MontoMensual)
        .filter(MontoMensual.mes == mes, MontoMensual.anio == anio, MontoMensual.profesor_id.isnot(None))
        .all()
    )
    esperado_por_prof = {m.profesor_id: m.total for m in montos}

    # Pagos ya registrados este periodo.
    pagos = (
        db.query(Pago)
        .filter(Pago.mes == mes, Pago.anio == anio)
        .all()
    )
    pago_por_prof = {p.profesor_id: p for p in pagos}

    filas = []
    for prof in profesores:
        factura = mejor_por_rfc.get(prof.rfc)
        pago = pago_por_prof.get(prof.id)
        filas.append({
            "profesor_id": str(prof.id),
            "nombre": prof.nombre,
            "rfc": prof.rfc,
            "activo": prof.activo,
            "factura_estado": factura.estado if factura else None,
            "factura_total": _fmt(factura.total) if factura else None,
            "esperado": _fmt(esperado_por_prof.get(prof.id)),
            "pagada": bool(pago.pagada) if pago else False,
            "fecha_pago": pago.fecha_pago.isoformat() if pago and pago.fecha_pago else None,
            "metodo_pago": pago.metodo_pago if pago else None,
            "monto_pagado": _fmt(pago.monto_pagado) if pago else None,
            "registrado_por": pago.registrado_por if pago else None,
        })
    return filas


def _es_mejor(nueva: Factura, actual: Factura) -> bool:
    pn = _PRIORIDAD_ESTADO.get(nueva.estado, 0)
    pa = _PRIORIDAD_ESTADO.get(actual.estado, 0)
    if pn != pa:
        return pn > pa
    # A igual estado, la más reciente.
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (nueva.created_at or epoch) > (actual.created_at or epoch)
