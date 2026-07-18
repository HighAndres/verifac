"""
Correo de confirmación al profesor cuando su factura queda APROBADA.

Reglas:
- Solo facturas con estado "aprobada" (las rechazadas no generan correo).
- Solo una vez por factura (se registra en factura.confirmacion_enviada).
- Solo si el interruptor "confirmaciones_activas" está encendido en la
  configuración de correo Y hay App Password configurado.
- Un fallo de envío nunca rompe la validación: se registra y se reintenta
  en el siguiente evento (es idempotente).

Se envía por SMTP con la misma cuenta de Google del watcher IMAP.
"""
import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.factura import Factura
from app.models.profesor import Profesor
from app.services.config_correo import obtener_config, password_configurado

logger = logging.getLogger(__name__)

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _cuerpo(profesor: Profesor, f: Factura) -> tuple[str, str]:
    periodo = (
        f"{MESES[f.fecha_emision.month - 1]} de {f.fecha_emision.year}"
        if f.fecha_emision else "el periodo"
    )
    asunto = f"Factura aprobada — {periodo}"
    cuerpo = f"""Estimado(a) {profesor.nombre}:

Su factura fue recibida y APROBADA para continuar el proceso de pago.

    Folio fiscal (UUID): {f.uuid_cfdi}
    Fecha de emisión:    {f.fecha_emision.strftime('%d/%m/%Y') if f.fecha_emision else '—'}
    Total:               ${float(f.total or 0):,.2f} MXN
    Periodo:             {periodo}

No necesita realizar ninguna acción adicional.

Este es un mensaje automático de Verifac; por favor no responda a este correo.
"""
    return asunto, cuerpo


def _enviar_smtp(destinatario: str, asunto: str, cuerpo: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.IMAP_USER
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.set_content(cuerpo)
    with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        smtp.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
        smtp.send_message(msg)


def _facturas_pendientes(db: Session) -> list[Factura]:
    # Ventana de recencia: solo facturas validadas en los últimos 7 días. Evita
    # que, al activar el envío, se manden correos de meses históricos.
    limite = datetime.now(timezone.utc) - timedelta(days=7)
    return (
        db.query(Factura)
        .filter(
            Factura.estado == "aprobada",
            Factura.confirmacion_enviada.is_(None),
            Factura.fecha_validacion >= limite,
        )
        .all()
    )


def contar_pendientes(db: Session) -> int:
    """Cuántas confirmaciones se enviarían (facturas con profesor y correo)."""
    total = 0
    for f in _facturas_pendientes(db):
        profesor = db.query(Profesor).filter(Profesor.rfc == f.rfc_emisor).first()
        if profesor and profesor.correo:
            total += 1
    return total


def procesar_confirmaciones(db: Session, forzar: bool = False) -> dict:
    """Envía confirmaciones pendientes (aprobadas sin correo enviado). Idempotente.

    Con `forzar=True` (botón manual) se ignora el interruptor de envío
    automático; la contraseña del buzón sigue siendo requisito.
    """
    cfg = obtener_config(db)
    if not forzar and not cfg.confirmaciones_activas:
        return {"enviadas": 0, "errores": 0, "motivo": "confirmaciones automáticas desactivadas"}
    if not password_configurado():
        return {"enviadas": 0, "errores": 0, "motivo": "correo no configurado"}

    pendientes = _facturas_pendientes(db)

    enviadas = 0
    errores = 0
    for f in pendientes:
        # Copia local: tras un rollback el objeto queda expirado y accederlo truena.
        uuid_corto = f.uuid_cfdi[:8]
        profesor = db.query(Profesor).filter(Profesor.rfc == f.rfc_emisor).first()
        if not profesor or not profesor.correo:
            continue
        destinatario = profesor.correo
        try:
            asunto, cuerpo = _cuerpo(profesor, f)
            _enviar_smtp(destinatario, asunto, cuerpo)
            f.confirmacion_enviada = datetime.now(timezone.utc)
            db.commit()
            enviadas += 1
            logger.info("Confirmación enviada a %s (factura %s)", destinatario, uuid_corto)
        except Exception:
            db.rollback()
            errores += 1
            logger.exception("No se pudo enviar confirmación de %s", uuid_corto)

    return {"enviadas": enviadas, "errores": errores, "pendientes": len(pendientes)}
