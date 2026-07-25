"""Registro de una factura subida por el propio profesor desde su portal.

Reutiliza el validador (validar_cfdi) y el cotejo PDF↔XML (cotejar_pdf), igual que
el watcher IMAP, pero con dos candados: la factura debe ser del RFC del profesor
autenticado, y trae PDF (el portal lo exige). origen="portal" para distinguirla.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.factura import Factura
from app.models.profesor import Profesor
from app.models.validacion_detalle import ValidacionDetalle
from app.services.cfdi_parser import CFDIData
from app.services.pdf_cotejo import cotejar_pdf
from app.services.validador import validar_cfdi


class FacturaAjena(Exception):
    """El RFC emisor del XML no coincide con el del profesor."""


class FacturaDuplicada(Exception):
    """Ya existe una factura con ese UUID."""


def registrar_factura_portal(cfdi: CFDIData, pdf_bytes: bytes, profesor: Profesor,
                             db: Session) -> Factura:
    if not cfdi.uuid:
        raise ValueError("El CFDI no tiene TimbreFiscalDigital (UUID)")

    if (cfdi.rfc_emisor or "").upper() != profesor.rfc.upper():
        raise FacturaAjena(
            f"El RFC emisor del XML ({cfdi.rfc_emisor}) no es el tuyo ({profesor.rfc}). "
            "Solo puedes subir tus propias facturas."
        )

    if db.query(Factura).filter(Factura.uuid_cfdi == cfdi.uuid).first():
        raise FacturaDuplicada(f"La factura con folio {cfdi.uuid} ya está registrada.")

    detalles_data, estado, motivo = validar_cfdi(cfdi, db)

    # Cotejo del PDF adjunto contra el UUID del XML (mismo candado que el watcher).
    pdf_cotejo = cotejar_pdf(cfdi.uuid, [pdf_bytes] if pdf_bytes else [])
    if pdf_cotejo == "no_coincide":
        detalles_data.append({
            "campo": "Cotejo PDF↔XML",
            "valor_recibido": "PDF no corresponde",
            "valor_esperado": f"UUID {cfdi.uuid[:8]}…",
            "resultado": False,
            "mensaje": "El PDF adjunto no contiene el folio fiscal (UUID) del XML.",
        })
    fallidos = [d["campo"] for d in detalles_data if not d["resultado"]]
    estado = "rechazada" if fallidos else "aprobada"
    motivo = f"Campos con error: {', '.join(fallidos)}" if fallidos else None

    primer = cfdi.conceptos[0] if cfdi.conceptos else None
    factura = Factura(
        uuid_cfdi=cfdi.uuid,
        rfc_emisor=cfdi.rfc_emisor,
        nombre_emisor=cfdi.nombre_emisor,
        regimen_emisor=cfdi.regimen_fiscal,
        rfc_receptor=cfdi.rfc_receptor,
        nombre_receptor=cfdi.nombre_receptor,
        moneda=cfdi.moneda,
        fecha_emision=cfdi.fecha,
        fecha_timbrado=cfdi.fecha_timbrado,
        subtotal=cfdi.subtotal,
        iva_trasladado=cfdi.iva_trasladado,
        iva_retenido=cfdi.iva_retenido,
        isr_retenido=cfdi.isr_retenido,
        total=cfdi.total,
        clave_servicio=primer.clave_prod_serv if primer else None,
        clave_unidad=primer.clave_unidad if primer else None,
        descripcion_concepto=primer.descripcion if primer else None,
        forma_pago=cfdi.forma_pago,
        metodo_pago=cfdi.metodo_pago,
        uso_cfdi=cfdi.uso_cfdi,
        estado=estado,
        motivo_rechazo=motivo,
        fecha_validacion=datetime.now(timezone.utc),
        origen="portal",
        pdf_cotejo=pdf_cotejo,
    )
    db.add(factura)
    db.flush()
    for d in detalles_data:
        db.add(ValidacionDetalle(factura_id=factura.id, **d))
    db.commit()
    db.refresh(factura)
    return factura
