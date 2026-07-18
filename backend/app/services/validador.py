"""
Motor de validación CFDI 4.0.
Los nombres de campo coinciden exactamente con las columnas del archivo "Ejemplo Base BBVA.xlsx".
"""
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.catalogo_clave import CatalogoClave
from app.models.monto_mensual import MontoMensual
from app.models.profesor import Profesor
from app.models.profesor_clave import ProfesorClave
from app.services.cfdi_parser import CFDIData

# ── Reglas fijas de negocio ───────────────────────────────────────────────────
CLAVES_UNIDAD_VALIDAS = {"E48", "ACT"}
IVA_TASA = Decimal("0.16")
TOLERANCIA = Decimal(str(settings.TOLERANCIA_MONTO))   # margen de redondeo (configurable)
FORMA_PAGO_ESPERADA = "03"     # Transferencia electrónica
METODO_PAGO_ESPERADO = "PUE"   # Pago en una sola exhibición
MONEDA_ESPERADA = "MXN"
USO_CFDI_ESPERADO = "G03"


def _cerca(recibido: Decimal, esperado: Decimal) -> bool:
    return abs(recibido - esperado) <= TOLERANCIA


def _claves_servicio_autorizadas(profesor: Optional[Profesor], db: Session) -> set[str]:
    """
    Si el profesor tiene claves propias → usar esas (override).
    Si no → catálogo global tipo 'servicio' activo.
    """
    if profesor:
        pivot = db.query(ProfesorClave).filter(ProfesorClave.profesor_id == profesor.id).all()
        if pivot:
            ids = {p.catalogo_clave_id for p in pivot}
            return {c.clave for c in db.query(CatalogoClave).filter(CatalogoClave.id.in_(ids)).all()}

    return {
        c.clave
        for c in db.query(CatalogoClave)
        .filter(CatalogoClave.tipo == "servicio", CatalogoClave.activo == True)  # noqa: E712
        .all()
    }


def validar_cfdi(cfdi: CFDIData, db: Session) -> tuple[list[dict], str, Optional[str]]:
    """
    Retorna (detalles, estado, motivo_rechazo).
    Los nombres de campo siguen las columnas del Ejemplo Base BBVA.
    """
    detalles: list[dict] = []
    errores: list[str] = []

    def check(campo: str, recibido: str, esperado: str, ok: bool, mensaje: Optional[str] = None) -> None:
        detalles.append({
            "campo": campo,
            "valor_recibido": recibido,
            "valor_esperado": esperado,
            "resultado": ok,
            "mensaje": mensaje,
        })
        if not ok:
            errores.append(campo)

    # ── Nombre receptor ───────────────────────────────────────────────────────
    # Validamos por RFC, mostramos nombre para que coincida con el Excel
    check(
        "Nombre receptor",
        cfdi.nombre_receptor or cfdi.rfc_receptor,
        settings.NOMBRE_RECEPTOR,
        cfdi.rfc_receptor == settings.RFC_RECEPTOR,
    )

    # ── Uso CFDI ──────────────────────────────────────────────────────────────
    check("Uso CFDI", cfdi.uso_cfdi, USO_CFDI_ESPERADO, cfdi.uso_cfdi == USO_CFDI_ESPERADO)

    # ── Moneda ────────────────────────────────────────────────────────────────
    check("Moneda", cfdi.moneda, MONEDA_ESPERADA, cfdi.moneda == MONEDA_ESPERADA)

    # ── Forma de pago ─────────────────────────────────────────────────────────
    check(
        "Forma de pago",
        cfdi.forma_pago or "",
        FORMA_PAGO_ESPERADA,
        cfdi.forma_pago == FORMA_PAGO_ESPERADA,
        "03 = Transferencia electrónica de fondos",
    )

    # ── Método de pago ────────────────────────────────────────────────────────
    check(
        "Método de pago",
        cfdi.metodo_pago or "",
        METODO_PAGO_ESPERADO,
        cfdi.metodo_pago == METODO_PAGO_ESPERADO,
        "PUE = Pago en una sola exhibición",
    )

    # ── Nombre emisor (RFC registrado en sistema) ─────────────────────────────
    profesor = (
        db.query(Profesor)
        .filter(Profesor.rfc == cfdi.rfc_emisor, Profesor.activo == True)  # noqa: E712
        .first()
    )
    check(
        "Nombre emisor",
        cfdi.nombre_emisor,
        "Registrado en sistema",
        profesor is not None,
        "Agregar al catálogo de profesores para validación completa" if not profesor else None,
    )

    # ── Clave régimen emisor ──────────────────────────────────────────────────
    if profesor:
        check(
            "Clave régimen emisor",
            cfdi.regimen_fiscal,
            profesor.regimen_fiscal,
            cfdi.regimen_fiscal == profesor.regimen_fiscal,
        )

    # ── Clave de servicio y Unidad por concepto ───────────────────────────────
    claves_servicio = _claves_servicio_autorizadas(profesor, db)
    claves_desc = ", ".join(sorted(claves_servicio)) or "(ninguna registrada)"

    for i, concepto in enumerate(cfdi.conceptos):
        sufijo = f" [{i}]" if len(cfdi.conceptos) > 1 else ""

        check(
            f"Clave de servicio{sufijo}",
            concepto.clave_prod_serv,
            claves_desc,
            concepto.clave_prod_serv in claves_servicio,
        )

        check(
            f"Unidad{sufijo}",
            concepto.clave_unidad,
            ", ".join(sorted(CLAVES_UNIDAD_VALIDAS)),
            concepto.clave_unidad in CLAVES_UNIDAD_VALIDAS,
        )

    # ── IVA Trasladado ────────────────────────────────────────────────────────
    if cfdi.regimen_fiscal != "603":
        iva_esp = (cfdi.subtotal * IVA_TASA).quantize(Decimal("0.01"))
        check(
            "IVA Trasladado",
            str(cfdi.iva_trasladado),
            str(iva_esp),
            _cerca(cfdi.iva_trasladado, iva_esp),
            "16% del subtotal",
        )
    else:
        check("IVA Trasladado", str(cfdi.iva_trasladado), "0.00",
              cfdi.iva_trasladado == Decimal("0"), "Régimen 603 no causa IVA")

    # ── Retenciones por régimen ───────────────────────────────────────────────
    if cfdi.regimen_fiscal == "626":
        isr_esp = (cfdi.subtotal * Decimal("0.0125")).quantize(Decimal("0.01"))
        iva_ret_esp = (cfdi.subtotal * IVA_TASA * Decimal("2") / Decimal("3")).quantize(Decimal("0.01"))
        check("ISR retenido", str(cfdi.isr_retenido), str(isr_esp),
              _cerca(cfdi.isr_retenido, isr_esp), "1.25% del subtotal (RESICO)")
        check("IVA Retenido", str(cfdi.iva_retenido), str(iva_ret_esp),
              _cerca(cfdi.iva_retenido, iva_ret_esp), "2/3 del IVA trasladado")

    elif cfdi.regimen_fiscal == "612":
        isr_esp = (cfdi.subtotal * Decimal("0.10")).quantize(Decimal("0.01"))
        iva_ret_esp = (cfdi.subtotal * IVA_TASA * Decimal("2") / Decimal("3")).quantize(Decimal("0.01"))
        check("ISR retenido", str(cfdi.isr_retenido), str(isr_esp),
              _cerca(cfdi.isr_retenido, isr_esp), "10% del subtotal")
        check("IVA Retenido", str(cfdi.iva_retenido), str(iva_ret_esp),
              _cerca(cfdi.iva_retenido, iva_ret_esp), "2/3 del IVA trasladado")

    elif cfdi.regimen_fiscal == "603":
        check("ISR retenido", str(cfdi.isr_retenido), "0.00",
              cfdi.isr_retenido == Decimal("0"), "Régimen 603 no genera retenciones")
        check("IVA Retenido", str(cfdi.iva_retenido), "0.00",
              cfdi.iva_retenido == Decimal("0"), "Régimen 603 no genera retenciones")

    # ── Total ─────────────────────────────────────────────────────────────────
    # Fórmula Excel: Subtotal + IVA Trasladado − IVA Retenido − ISR retenido
    total_esp = (cfdi.subtotal + cfdi.iva_trasladado - cfdi.iva_retenido - cfdi.isr_retenido).quantize(Decimal("0.01"))
    check(
        "Total",
        str(cfdi.total),
        str(total_esp),
        _cerca(cfdi.total, total_esp),
        "Subtotal + IVA Trasladado − IVA Retenido − ISR retenido",
    )

    # ── Fecha de emisión ──────────────────────────────────────────────────────
    check(
        "Fecha de emisión",
        cfdi.fecha.strftime("%Y-%m-%d") if cfdi.fecha else "",
        "Fecha válida",
        cfdi.fecha is not None,
    )

    # ── Conciliación contra layout de montos mensuales ────────────────────────
    # Regla crítica: si el emisor está registrado, la factura DEBE conciliarse contra
    # el layout del mes/año de su fecha de emisión. Si el XML no trae fecha, o no hay
    # layout cargado para ese periodo, se RECHAZA — nunca se aprueba sin conciliar.
    if profesor:
        if not cfdi.fecha:
            check(
                "Conciliación (layout)",
                "sin fecha de emisión",
                "Fecha válida para ubicar el mes",
                False,
                "El CFDI no tiene fecha de emisión; no se puede ubicar el layout del mes.",
            )
        else:
            periodo = f"{cfdi.fecha.month:02d}/{cfdi.fecha.year}"
            monto_ref = (
                db.query(MontoMensual)
                .filter(
                    MontoMensual.profesor_id == profesor.id,
                    MontoMensual.mes == cfdi.fecha.month,
                    MontoMensual.anio == cfdi.fecha.year,
                )
                .first()
            )
            if not monto_ref:
                check(
                    "Conciliación (layout)",
                    f"Emisión {periodo}",
                    "Layout de montos cargado",
                    False,
                    f"No hay layout de montos para este emisor en {periodo}. "
                    "Verifica que el XML sea del mes correcto y que el layout de ese mes esté cargado.",
                )
            else:
                check(
                    "Subtotal (layout)",
                    str(cfdi.subtotal),
                    str(monto_ref.subtotal),
                    _cerca(cfdi.subtotal, Decimal(str(monto_ref.subtotal))),
                    "Cotejado contra layout de montos del mes",
                )
                check(
                    "IVA Trasladado (layout)",
                    str(cfdi.iva_trasladado),
                    str(monto_ref.iva_trasladado),
                    _cerca(cfdi.iva_trasladado, Decimal(str(monto_ref.iva_trasladado))),
                    "Cotejado contra layout de montos del mes",
                )
                check(
                    "IVA Retenido (layout)",
                    str(cfdi.iva_retenido),
                    str(monto_ref.iva_retenido),
                    _cerca(cfdi.iva_retenido, Decimal(str(monto_ref.iva_retenido))),
                    "Cotejado contra layout de montos del mes",
                )
                check(
                    "Total (layout)",
                    str(cfdi.total),
                    str(monto_ref.total),
                    _cerca(cfdi.total, Decimal(str(monto_ref.total))),
                    "Cotejado contra layout de montos del mes",
                )

    estado = "aprobada" if not errores else "rechazada"
    motivo = f"Campos con error: {', '.join(errores)}" if errores else None
    return detalles, estado, motivo
