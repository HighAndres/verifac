"""
Revalidación de facturas ya guardadas (candado #4).

Reconstruye un CFDIData a partir de los campos almacenados en la factura y vuelve
a correr el motor de validación contra las reglas y el layout de montos ACTUALES.
Sirve para facturas que se rechazaron por falta de layout y que ahora ya se pueden
conciliar, sin depender del XML original.

Limitación conocida: solo se conserva el primer concepto; CFDIs multi-concepto se
revalidan con ese primer concepto. El veredicto del cotejo PDF↔XML no se puede
recomputar sin el PDF, así que se reaplica el resultado guardado en la factura.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.factura import Factura
from app.models.validacion_detalle import ValidacionDetalle
from app.services.cfdi_parser import CFDIData, ConceptoCFDI
from app.services.validador import validar_cfdi


def _d(val) -> Decimal:
    return Decimal(str(val or 0))


def reconstruir_cfdi(f: Factura) -> CFDIData:
    conceptos = []
    if f.clave_servicio or f.clave_unidad:
        conceptos = [ConceptoCFDI(
            clave_prod_serv=f.clave_servicio or "",
            clave_unidad=f.clave_unidad or "",
            descripcion=f.descripcion_concepto or "",
            valor_unitario=_d(f.subtotal),
            objeto_imp="02",
        )]
    return CFDIData(
        fecha=f.fecha_emision,
        subtotal=_d(f.subtotal),
        total=_d(f.total),
        forma_pago=f.forma_pago,
        metodo_pago=f.metodo_pago,
        rfc_emisor=f.rfc_emisor,
        nombre_emisor=f.nombre_emisor or "",
        regimen_fiscal=f.regimen_emisor or "",
        rfc_receptor=f.rfc_receptor or settings.RFC_RECEPTOR,
        nombre_receptor=f.nombre_receptor or settings.NOMBRE_RECEPTOR,
        uso_cfdi=f.uso_cfdi or "",
        moneda=f.moneda or "MXN",
        conceptos=conceptos,
        iva_trasladado=_d(f.iva_trasladado),
        isr_retenido=_d(f.isr_retenido),
        iva_retenido=_d(f.iva_retenido),
        uuid=f.uuid_cfdi,
        fecha_timbrado=f.fecha_timbrado,
    )


def revalidar_factura(f: Factura, db: Session) -> tuple[str, Optional[str]]:
    """Revalida una factura in-place (no hace commit). Retorna (estado, motivo)."""
    cfdi = reconstruir_cfdi(f)
    detalles_data, _, _ = validar_cfdi(cfdi, db)

    # El cotejo PDF↔XML no se puede rehacer sin el PDF; se reaplica el guardado.
    if f.pdf_cotejo == "no_coincide":
        detalles_data.append({
            "campo": "Cotejo PDF↔XML",
            "valor_recibido": "PDF no corresponde",
            "valor_esperado": f"UUID {f.uuid_cfdi[:8]}…",
            "resultado": False,
            "mensaje": "El PDF adjunto no contiene el UUID del XML.",
        })

    fallidos = [d["campo"] for d in detalles_data if not d["resultado"]]
    estado = "rechazada" if fallidos else "aprobada"
    motivo = f"Campos con error: {', '.join(fallidos)}" if fallidos else None

    db.query(ValidacionDetalle).filter(ValidacionDetalle.factura_id == f.id).delete()
    for d in detalles_data:
        db.add(ValidacionDetalle(factura_id=f.id, **d))

    f.estado = estado
    f.motivo_rechazo = motivo
    f.fecha_validacion = datetime.now(timezone.utc)
    return estado, motivo
