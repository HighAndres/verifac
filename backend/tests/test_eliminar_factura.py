"""Borrado de facturas defectuosas (solo superadmin): libera el UUID para que
el profesor pueda volver a subir su factura corregida, con rastro en bitácora."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.audit_log import AuditLog
from app.models.factura import Factura
from app.models.usuario import Usuario
from app.models.validacion_detalle import ValidacionDetalle


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _headers(db, username, rol):
    db.add(Usuario(username=username, nombre=username, password_hash=hash_password("x"),
                   rol=rol, activo=True))
    db.flush()
    return {"Authorization": f"Bearer {create_access_token(username, rol)}"}


def _factura(db, uuid_cfdi="DEL-UUID-1"):
    f = Factura(uuid_cfdi=uuid_cfdi, rfc_emisor="XAXX010101000", nombre_emisor="TEST",
                estado="rechazada", motivo_rechazo="Campos con error: IVA Retenido",
                total=1000, origen="portal",
                fecha_emision=datetime(2026, 10, 10, tzinfo=timezone.utc))
    db.add(f)
    db.flush()
    db.add(ValidacionDetalle(factura_id=f.id, campo="IVA Retenido",
                             valor_recibido="100", valor_esperado="106.67", resultado=False))
    db.flush()
    return f


def test_superadmin_elimina_factura_con_detalles_y_bitacora(client, db):
    headers = _headers(db, "admin_del", "superadmin")
    f = _factura(db)
    factura_id = f.id

    r = client.delete(f"/api/v1/facturas/{factura_id}", headers=headers)
    assert r.status_code == 204

    assert db.query(Factura).filter(Factura.id == factura_id).first() is None
    assert db.query(ValidacionDetalle).filter(ValidacionDetalle.factura_id == factura_id).count() == 0

    log = (
        db.query(AuditLog)
        .filter(AuditLog.accion == "DELETE", AuditLog.recurso == "factura",
                AuditLog.recurso_id == "DEL-UUID-1")
        .first()
    )
    assert log is not None
    assert log.username == "admin_del"


def test_revisor_no_puede_eliminar_facturas(client, db):
    headers = _headers(db, "rev_del", "revisor")
    f = _factura(db, uuid_cfdi="DEL-UUID-2")
    r = client.delete(f"/api/v1/facturas/{f.id}", headers=headers)
    assert r.status_code == 403
    assert db.query(Factura).filter(Factura.id == f.id).first() is not None


def test_eliminar_factura_inexistente_404(client, db):
    headers = _headers(db, "admin_del2", "superadmin")
    r = client.delete("/api/v1/facturas/00000000-0000-0000-0000-000000000099", headers=headers)
    assert r.status_code == 404
