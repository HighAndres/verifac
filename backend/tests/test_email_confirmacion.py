"""Pruebas del correo de confirmación a profesores (SMTP simulado)."""
from datetime import datetime, timezone

import app.services.email_confirmacion as ec
from app.models.factura import Factura
from app.services.config_correo import obtener_config
from tests.factories import add_profesor, build_cfdi


def _factura(db, cfdi, estado):
    f = Factura(
        uuid_cfdi=cfdi.uuid, rfc_emisor=cfdi.rfc_emisor, nombre_emisor=cfdi.nombre_emisor,
        regimen_emisor=cfdi.regimen_fiscal, fecha_emision=cfdi.fecha,
        subtotal=cfdi.subtotal, total=cfdi.total, estado=estado,
        origen="xml", pdf_cotejo="sin_pdf", fecha_validacion=datetime.now(timezone.utc),
    )
    db.add(f)
    db.flush()
    return f


def _preparar(db, monkeypatch, activas=True):
    """Activa confirmaciones, simula password, captura envíos SMTP y drena
    cualquier pendiente preexistente de la BD para aislar la prueba."""
    cfg = obtener_config(db)
    cfg.confirmaciones_activas = True
    db.flush()
    monkeypatch.setattr(ec, "password_configurado", lambda: True)
    enviados = []
    monkeypatch.setattr(ec, "_enviar_smtp", lambda dest, asunto, cuerpo: enviados.append((dest, asunto)))
    ec.procesar_confirmaciones(db)   # drena facturas reales pendientes (si las hay)
    enviados.clear()
    cfg.confirmaciones_activas = activas
    db.flush()
    return enviados


def test_solo_aprobadas_reciben_correo(db, monkeypatch):
    enviados = _preparar(db, monkeypatch)
    p = add_profesor(db, rfc="MAIL010101AA1", nombre="PROFE MAIL", regimen="612")
    _factura(db, build_cfdi(rfc_emisor=p.rfc, uuid="MAIL-OK"), "aprobada")
    _factura(db, build_cfdi(rfc_emisor=p.rfc, uuid="MAIL-BAD"), "rechazada")

    r = ec.procesar_confirmaciones(db)
    assert r["enviadas"] == 1
    assert enviados[0][0] == "test@example.com"          # correo del profesor
    assert "aprobada" in enviados[0][1].lower()


def test_solo_una_vez_por_factura(db, monkeypatch):
    enviados = _preparar(db, monkeypatch)
    p = add_profesor(db, rfc="MAIL010101BB2", regimen="612")
    _factura(db, build_cfdi(rfc_emisor=p.rfc, uuid="MAIL-UNA"), "aprobada")

    assert ec.procesar_confirmaciones(db)["enviadas"] == 1
    assert ec.procesar_confirmaciones(db)["enviadas"] == 0   # segunda corrida: nada
    assert len(enviados) == 1


def test_interruptor_apagado_no_envia(db, monkeypatch):
    enviados = _preparar(db, monkeypatch, activas=False)
    p = add_profesor(db, rfc="MAIL010101CC3", regimen="612")
    _factura(db, build_cfdi(rfc_emisor=p.rfc, uuid="MAIL-OFF"), "aprobada")

    r = ec.procesar_confirmaciones(db)
    assert r["enviadas"] == 0
    assert enviados == []


def test_fallo_smtp_no_marca_enviada(db, monkeypatch):
    _preparar(db, monkeypatch)
    def _falla(dest, asunto, cuerpo):
        raise ConnectionError("SMTP caído")
    monkeypatch.setattr(ec, "_enviar_smtp", _falla)
    p = add_profesor(db, rfc="MAIL010101DD4", regimen="612")
    _factura(db, build_cfdi(rfc_emisor=p.rfc, uuid="MAIL-ERR"), "aprobada")

    r = ec.procesar_confirmaciones(db)
    assert r["errores"] == 1
    # Ninguna factura quedó marcada como confirmada (se reintentará después).
    marcadas = (
        db.query(Factura)
        .filter(Factura.uuid_cfdi == "MAIL-ERR", Factura.confirmacion_enviada.isnot(None))
        .count()
    )
    assert marcadas == 0
