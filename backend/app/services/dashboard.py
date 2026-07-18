"""Agregados del mes para el panorama (dashboard) de operación."""
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models.factura import Factura
from app.models.monto_mensual import MontoMensual
from app.models.profesor import Profesor


def resumen_mes(db: Session, mes: int, anio: int) -> dict:
    del_mes = [
        extract("month", Factura.fecha_emision) == mes,
        extract("year", Factura.fecha_emision) == anio,
    ]

    por_estado = dict(
        db.query(Factura.estado, func.count())
        .filter(*del_mes)
        .group_by(Factura.estado)
        .all()
    )
    aprobadas = por_estado.get("aprobada", 0)
    rechazadas = por_estado.get("rechazada", 0)
    total_facturas = sum(por_estado.values())

    aprobado_total = db.query(func.coalesce(func.sum(Factura.total), 0)).filter(
        *del_mes, Factura.estado == "aprobada"
    ).scalar()

    montos = (
        db.query(MontoMensual)
        .filter(MontoMensual.mes == mes, MontoMensual.anio == anio)
        .all()
    )
    esperado_total = sum((Decimal(str(m.total)) for m in montos), Decimal("0"))
    sin_match = sum(1 for m in montos if m.profesor_id is None)

    # Profesores con monto esperado que aún no tienen factura APROBADA este mes.
    rfc_aprobados = {
        r[0]
        for r in db.query(Factura.rfc_emisor)
        .filter(*del_mes, Factura.estado == "aprobada")
        .all()
    }
    pendientes = []
    for m in montos:
        if m.profesor_id is None:
            continue
        prof = db.get(Profesor, m.profesor_id)
        if prof and prof.rfc not in rfc_aprobados:
            pendientes.append({
                "nombre": prof.nombre,
                "rfc": prof.rfc,
                "esperado": float(m.total),
            })
    pendientes.sort(key=lambda p: p["nombre"])

    ultimas = (
        db.query(Factura)
        .filter(*del_mes)
        .order_by(Factura.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "mes": mes,
        "anio": anio,
        "facturas": {
            "total": total_facturas,
            "aprobadas": aprobadas,
            "rechazadas": rechazadas,
            "otras": total_facturas - aprobadas - rechazadas,
        },
        "montos": {
            "profesores_en_layout": len(montos),
            "sin_match": sin_match,
            "esperado_total": float(esperado_total),
            "aprobado_total": float(aprobado_total),
        },
        "pendientes_envio": pendientes,
        "ultimas_facturas": [
            {
                "id": str(f.id),
                "nombre_emisor": f.nombre_emisor,
                "total": float(f.total or 0),
                "estado": f.estado,
                "fecha_emision": f.fecha_emision.isoformat() if f.fecha_emision else None,
            }
            for f in ultimas
        ],
    }
