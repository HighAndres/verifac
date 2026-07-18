"""
Watcher IMAP para honorarios@thehumantalent.com (Google Workspace).
Detecta correos no leídos con adjuntos XML o ZIP, extrae los XML CFDI 4.0,
los valida y guarda el resultado en la BD. Marca el correo como leído al final.
"""
import email
import email.utils
import imaplib
import io
import logging
import zipfile
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.factura import Factura
from app.models.validacion_detalle import ValidacionDetalle
from app.services.cfdi_parser import parsear_cfdi
from app.services.pdf_cotejo import cotejar_pdf
from app.services.validador import validar_cfdi

logger = logging.getLogger(__name__)


# ── Extracción de adjuntos (XML y PDF) ────────────────────────────────────────

def _extraer_xmls(filename: str, data: bytes) -> list[tuple[str, bytes]]:
    """Devuelve lista de (nombre_archivo, bytes_xml) según el tipo de adjunto."""
    nombre = filename.lower()
    if nombre.endswith(".xml"):
        return [(filename, data)]
    if nombre.endswith(".zip"):
        resultado = []
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for entry in zf.namelist():
                    if entry.lower().endswith(".xml") and not entry.startswith("__"):
                        resultado.append((entry, zf.read(entry)))
        except zipfile.BadZipFile:
            logger.warning("ZIP corrupto o inválido: %s", filename)
        return resultado
    return []


def _extraer_pdfs(filename: str, data: bytes) -> list[bytes]:
    """Devuelve los PDFs contenidos en el adjunto (directo o dentro de un ZIP)."""
    nombre = filename.lower()
    if nombre.endswith(".pdf"):
        return [data]
    if nombre.endswith(".zip"):
        resultado = []
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for entry in zf.namelist():
                    if entry.lower().endswith(".pdf") and not entry.startswith("__"):
                        resultado.append(zf.read(entry))
        except zipfile.BadZipFile:
            pass
        return resultado
    return []


# ── Procesamiento de un solo XML ──────────────────────────────────────────────

def _procesar_xml(xml_nombre: str, xml_bytes: bytes, remitente: str, db: Session,
                  pdfs: list[bytes] | None = None) -> dict:
    """Parsea, valida y guarda una factura. Retorna resumen del resultado."""
    try:
        cfdi = parsear_cfdi(xml_bytes)
    except ValueError as exc:
        return {"archivo": xml_nombre, "ok": False, "error": str(exc)}

    if not cfdi.uuid:
        return {"archivo": xml_nombre, "ok": False, "error": "Sin TimbreFiscalDigital (UUID vacío)"}

    if db.query(Factura).filter(Factura.uuid_cfdi == cfdi.uuid).first():
        return {"archivo": xml_nombre, "ok": False, "error": f"UUID {cfdi.uuid[:8]}… ya registrado"}

    primer_concepto = cfdi.conceptos[0] if cfdi.conceptos else None
    detalles_data, estado, motivo = validar_cfdi(cfdi, db)

    # ── Candado #6: cotejo del PDF adjunto contra el XML ──────────────────────
    pdf_cotejo = cotejar_pdf(cfdi.uuid, pdfs or [])
    if pdf_cotejo == "no_coincide":
        detalles_data.append({
            "campo": "Cotejo PDF↔XML",
            "valor_recibido": "PDF no corresponde",
            "valor_esperado": f"UUID {cfdi.uuid[:8]}…",
            "resultado": False,
            "mensaje": "El PDF adjunto no contiene el UUID del XML.",
        })
    # Recomputar estado/motivo incluyendo el cotejo PDF
    fallidos = [d["campo"] for d in detalles_data if not d["resultado"]]
    estado = "rechazada" if fallidos else "aprobada"
    motivo = f"Campos con error: {', '.join(fallidos)}" if fallidos else None

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
        clave_servicio=primer_concepto.clave_prod_serv if primer_concepto else None,
        clave_unidad=primer_concepto.clave_unidad if primer_concepto else None,
        descripcion_concepto=primer_concepto.descripcion if primer_concepto else None,
        forma_pago=cfdi.forma_pago,
        metodo_pago=cfdi.metodo_pago,
        uso_cfdi=cfdi.uso_cfdi,
        estado=estado,
        motivo_rechazo=motivo,
        fecha_validacion=datetime.now(timezone.utc),
        origen="xml",
        pdf_cotejo=pdf_cotejo,
    )
    db.add(factura)
    db.flush()

    for d in detalles_data:
        db.add(ValidacionDetalle(factura_id=factura.id, **d))

    db.commit()
    db.refresh(factura)

    logger.info("Factura %s guardada — estado: %s — pdf: %s — emisor: %s",
                cfdi.uuid[:8], estado, pdf_cotejo, cfdi.nombre_emisor)
    return {
        "archivo": xml_nombre,
        "ok": True,
        "uuid": cfdi.uuid,
        "emisor": cfdi.nombre_emisor,
        "remitente": remitente,
        "estado": estado,
        "pdf_cotejo": pdf_cotejo,
    }


# ── Revisión del buzón ────────────────────────────────────────────────────────

def revisar_correo(db: Session, imap_host: str, imap_port: int, imap_user: str,
                   imap_password: str, imap_folder: str = "INBOX") -> dict:
    """
    Conecta al buzón IMAP, procesa todos los correos no leídos con adjuntos
    XML o ZIP, y marca cada correo como leído al terminar.
    """
    procesadas: list[dict] = []
    errores: list[dict] = []

    try:
        conn = imaplib.IMAP4_SSL(imap_host, imap_port)
        conn.login(imap_user, imap_password)
        conn.select(imap_folder)
    except imaplib.IMAP4.error as exc:
        logger.error("Error conectando al IMAP: %s", exc)
        return {"ok": False, "error": str(exc), "procesadas": [], "errores": []}

    try:
        _, ids = conn.search(None, "UNSEEN")
        email_ids = ids[0].split()
        logger.info("Correos no leídos encontrados: %d", len(email_ids))

        for eid in email_ids:
            _, msg_data = conn.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            remitente = email.utils.parseaddr(msg.get("From", ""))[1].lower()
            asunto = msg.get("Subject", "(sin asunto)")
            logger.info("Procesando correo de %s — asunto: %s", remitente, asunto)

            # Recolectar TODOS los XMLs y PDFs del correo antes de procesar,
            # para poder cotejar cada XML contra los PDFs adjuntos (candado #6).
            xmls_correo: list[tuple[str, bytes]] = []
            pdfs_correo: list[bytes] = []

            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                filename = part.get_filename()
                if not filename:
                    continue

                nombre_lower = filename.lower()
                if not nombre_lower.endswith((".xml", ".zip", ".pdf")):
                    continue

                payload = part.get_payload(decode=True)
                if not payload:
                    continue

                xmls_correo.extend(_extraer_xmls(filename, payload))
                pdfs_correo.extend(_extraer_pdfs(filename, payload))

            for xml_nombre, xml_bytes in xmls_correo:
                try:
                    resultado = _procesar_xml(xml_nombre, xml_bytes, remitente, db, pdfs_correo)
                    if resultado["ok"]:
                        procesadas.append(resultado)
                    else:
                        errores.append(resultado)
                except Exception as exc:
                    db.rollback()
                    logger.exception("Error procesando %s", xml_nombre)
                    errores.append({"archivo": xml_nombre, "ok": False, "error": str(exc)})

            if not xmls_correo:
                logger.info("Correo sin XML/ZIP procesable — se marca leído de todas formas")

            # Marcar como leído independientemente del resultado
            conn.store(eid, "+FLAGS", "\\Seen")

    finally:
        conn.logout()

    return {
        "ok": True,
        "revisados": len(email_ids),
        "procesadas": procesadas,
        "errores": errores,
        "total_procesadas": len(procesadas),
        "total_errores": len(errores),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
