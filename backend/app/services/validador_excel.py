"""
Validador para filas del Excel "Ejemplo Base BBVA".
Aplica las mismas reglas de negocio que el validador XML pero sobre datos tabulares.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.catalogo_clave import CatalogoClave
from app.models.factura import Factura
from app.models.profesor import Profesor
from app.models.validacion_detalle import ValidacionDetalle
from app.services.excel_parser import FilaExcel

CLAVES_UNIDAD_VALIDAS = {"E48", "ACT"}
IVA_TASA = Decimal("0.16")
TOLERANCIA = Decimal(str(settings.TOLERANCIA_MONTO))
FORMA_PAGO_ESP = "03"
METODO_PAGO_ESP = "PUE"
MONEDA_ESP = "MXN"
USO_CFDI_ESP = "G03"


def _cerca(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCIA


def _claves_servicio_globales(db: Session) -> set[str]:
    return {
        c.clave for c in db.query(CatalogoClave)
        .filter(CatalogoClave.tipo == "servicio", CatalogoClave.activo == True)  # noqa: E712
        .all()
    }


def procesar_fila(fila: FilaExcel, db: Session) -> dict:
    """
    Valida una fila del Excel, guarda la Factura y sus detalles de validación.
    Retorna resumen del resultado.
    """
    detalles: list[dict] = []
    errores: list[str] = []

    def check(campo: str, recibido: str, esperado: str, ok: bool, mensaje: Optional[str] = None):
        detalles.append({"campo": campo, "valor_recibido": recibido,
                         "valor_esperado": esperado, "resultado": ok, "mensaje": mensaje})
        if not ok:
            errores.append(campo)

    # ── Validaciones ─────────────────────────────────────────────────────────

    check("Nombre receptor", fila.nombre_receptor, settings.NOMBRE_RECEPTOR,
          fila.nombre_receptor.upper() == settings.NOMBRE_RECEPTOR.upper())

    check("Uso CFDI", fila.uso_cfdi, USO_CFDI_ESP, fila.uso_cfdi == USO_CFDI_ESP)

    check("Moneda", fila.moneda, MONEDA_ESP, fila.moneda == MONEDA_ESP)

    check("Forma de pago", fila.forma_pago, FORMA_PAGO_ESP,
          fila.forma_pago == FORMA_PAGO_ESP, "03 = Transferencia electrónica")

    check("Método de pago", fila.metodo_pago, METODO_PAGO_ESP,
          fila.metodo_pago == METODO_PAGO_ESP, "PUE = Pago en una sola exhibición")

    # Nombre emisor — buscar por nombre en profesores
    profesor = (
        db.query(Profesor)
        .filter(Profesor.nombre.ilike(fila.nombre_emisor), Profesor.activo == True)  # noqa: E712
        .first()
    )
    check("Nombre emisor", fila.nombre_emisor, "Registrado en sistema", profesor is not None,
          "Dar de alta en Profesores si no existe" if not profesor else None)

    regimen = fila.regimen_emisor
    if profesor:
        check("Clave régimen emisor", regimen, profesor.regimen_fiscal,
              regimen == profesor.regimen_fiscal)

    # Clave de servicio
    claves_ok = _claves_servicio_globales(db)
    check("Clave de servicio", fila.clave_servicio,
          ", ".join(sorted(claves_ok)) or "(ninguna)",
          fila.clave_servicio in claves_ok)

    # Unidad
    check("Unidad", fila.unidad, ", ".join(sorted(CLAVES_UNIDAD_VALIDAS)),
          fila.unidad in CLAVES_UNIDAD_VALIDAS)

    # IVA Trasladado
    if regimen != "603":
        iva_esp = (fila.subtotal * IVA_TASA).quantize(Decimal("0.01"))
        check("IVA Trasladado", str(fila.iva_trasladado), str(iva_esp),
              _cerca(fila.iva_trasladado, iva_esp), "16% del subtotal")
    else:
        check("IVA Trasladado", str(fila.iva_trasladado), "0.00",
              fila.iva_trasladado == Decimal("0"), "Régimen 603 no causa IVA")

    # Retenciones
    if regimen == "626":
        isr_esp = (fila.subtotal * Decimal("0.0125")).quantize(Decimal("0.01"))
        iva_ret_esp = (fila.subtotal * IVA_TASA * Decimal("2") / Decimal("3")).quantize(Decimal("0.01"))
        check("ISR retenido", str(fila.isr_retenido), str(isr_esp),
              _cerca(fila.isr_retenido, isr_esp), "1.25% del subtotal (RESICO)")
        check("IVA Retenido", str(fila.iva_retenido), str(iva_ret_esp),
              _cerca(fila.iva_retenido, iva_ret_esp), "2/3 del IVA trasladado")
    elif regimen == "612":
        isr_esp = (fila.subtotal * Decimal("0.10")).quantize(Decimal("0.01"))
        iva_ret_esp = (fila.subtotal * IVA_TASA * Decimal("2") / Decimal("3")).quantize(Decimal("0.01"))
        check("ISR retenido", str(fila.isr_retenido), str(isr_esp),
              _cerca(fila.isr_retenido, isr_esp), "10% del subtotal")
        check("IVA Retenido", str(fila.iva_retenido), str(iva_ret_esp),
              _cerca(fila.iva_retenido, iva_ret_esp), "2/3 del IVA trasladado")
    elif regimen == "603":
        check("ISR retenido", str(fila.isr_retenido), "0.00",
              fila.isr_retenido == Decimal("0"), "Régimen 603 sin retenciones")
        check("IVA Retenido", str(fila.iva_retenido), "0.00",
              fila.iva_retenido == Decimal("0"), "Régimen 603 sin retenciones")

    # Total
    total_esp = (fila.subtotal + fila.iva_trasladado - fila.iva_retenido - fila.isr_retenido).quantize(Decimal("0.01"))
    check("Total", str(fila.total), str(total_esp),
          _cerca(fila.total, total_esp), "Subtotal + IVA − IVA Retenido − ISR retenido")

    # ── Guardar factura ───────────────────────────────────────────────────────
    estado = "aprobada" if not errores else "rechazada"
    motivo = f"Campos con error: {', '.join(errores)}" if errores else None

    factura = Factura(
        uuid_cfdi=str(uuid.uuid4()),          # generado — no viene del SAT
        rfc_emisor=profesor.rfc if profesor else "DESCONOCIDO",
        nombre_emisor=fila.nombre_emisor,
        regimen_emisor=regimen,
        subtotal=fila.subtotal,
        iva_trasladado=fila.iva_trasladado,
        iva_retenido=fila.iva_retenido,
        isr_retenido=fila.isr_retenido,
        total=fila.total,
        clave_servicio=fila.clave_servicio,
        clave_unidad=fila.unidad,
        descripcion_concepto=fila.descripcion,
        forma_pago=fila.forma_pago,
        metodo_pago=fila.metodo_pago,
        uso_cfdi=fila.uso_cfdi,
        estado=estado,
        motivo_rechazo=motivo,
        fecha_validacion=datetime.now(timezone.utc),
        origen="captura_manual",   # no proviene de un CFDI real; UUID sintético
        pdf_cotejo="sin_pdf",
    )
    db.add(factura)
    db.flush()

    for d in detalles:
        db.add(ValidacionDetalle(factura_id=factura.id, **d))

    db.commit()
    db.refresh(factura)

    return {
        "fila": fila.fila,
        "nombre_emisor": fila.nombre_emisor,
        "categoria": fila.categoria,
        "subtotal": str(fila.subtotal),
        "estado": estado,
        "errores": errores,
        "factura_id": str(factura.id),
    }
