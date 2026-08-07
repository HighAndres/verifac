"""Pruebas del portal del profesor (rol 'profesor' + endpoints /portal).

Se usa TestClient con override de get_db para que la API vea los datos que el
test crea dentro de la transacción (que luego se revierte).
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.factura import Factura
from app.models.profesor import Profesor
from app.models.usuario import Usuario


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _profesor(db, rfc, nombre, correo, drive_url=None):
    p = Profesor(rfc=rfc, nombre=nombre, correo=correo, regimen_fiscal="612",
                 drive_url=drive_url, activo=True)
    db.add(p)
    db.flush()
    return p


def _usuario(db, username, rol, profesor_id=None):
    u = Usuario(username=username, nombre=username, password_hash=hash_password("x"),
                rol=rol, profesor_id=profesor_id, activo=True)
    db.add(u)
    db.flush()
    return u


def _factura(db, rfc, uuid, estado="aprobada", fecha=datetime(2026, 6, 15, tzinfo=timezone.utc)):
    f = Factura(uuid_cfdi=uuid, rfc_emisor=rfc, estado=estado, total=1000,
                fecha_emision=fecha, origen="xml")
    db.add(f)
    db.flush()
    return f


def _auth(username):
    return {"Authorization": f"Bearer {create_access_token(username, 'profesor')}"}


def test_mis_facturas_solo_del_profesor(client, db):
    p1 = _profesor(db, "AAA010101AA1", "Profe Uno", "uno@example.com", "https://drive.google.com/x")
    p2 = _profesor(db, "BBB020202BB2", "Profe Dos", "dos@example.com")
    _usuario(db, "profe1", "profesor", p1.id)
    _factura(db, p1.rfc, "UUID-P1-1")
    _factura(db, p1.rfc, "UUID-P1-2", estado="rechazada")
    _factura(db, p2.rfc, "UUID-P2-1")  # de otro profesor, no debe aparecer

    r = client.get("/api/v1/portal/mis-facturas", headers=_auth("profe1"))
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert {f["uuid_cfdi"] for f in data["items"]} == {"UUID-P1-1", "UUID-P1-2"}


def test_mi_perfil_incluye_drive_url(client, db):
    p = _profesor(db, "CCC030303CC3", "Profe Tres", "tres@example.com", "https://drive.google.com/carpeta")
    _usuario(db, "profe3", "profesor", p.id)

    r = client.get("/api/v1/portal/mi-perfil", headers=_auth("profe3"))
    assert r.status_code == 200
    assert r.json()["drive_url"] == "https://drive.google.com/carpeta"


def test_mi_factura_ajena_da_404(client, db):
    p1 = _profesor(db, "DDD040404DD4", "Profe Cuatro", "cuatro@example.com")
    p2 = _profesor(db, "EEE050505EE5", "Profe Cinco", "cinco@example.com")
    _usuario(db, "profe4", "profesor", p1.id)
    ajena = _factura(db, p2.rfc, "UUID-AJENA")

    r = client.get(f"/api/v1/portal/mis-facturas/{ajena.id}", headers=_auth("profe4"))
    assert r.status_code == 404


def test_revisor_no_entra_al_portal(client, db):
    u = _usuario(db, "revisor1", "revisor")
    token = create_access_token(u.username, "revisor")
    r = client.get("/api/v1/portal/mis-facturas", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_profesor_sin_ligar_da_403(client, db):
    _usuario(db, "profe_suelto", "profesor", profesor_id=None)
    r = client.get("/api/v1/portal/mi-perfil", headers=_auth("profe_suelto"))
    assert r.status_code == 403


def test_mis_facturas_ordena_por_creacion_no_por_fecha_emision(client, db):
    # Caso real: se sube una factura, se rechaza, y luego se corrige y se vuelve a
    # subir (UUID distinto). La corregida se crea DESPUÉS pero puede traer una
    # fecha_emision del XML igual o anterior a la rechazada. La barra del portal
    # debe reflejar siempre la más reciente por fecha de PROCESO, no la del XML.
    p = _profesor(db, "FFF060606FF6", "Profe Seis", "seis@example.com")
    _usuario(db, "profe6", "profesor", p.id)
    _factura(db, p.rfc, "UUID-VIEJA-RECHAZADA", estado="rechazada",
             fecha=datetime(2026, 6, 20, tzinfo=timezone.utc))
    vieja = db.query(Factura).filter(Factura.uuid_cfdi == "UUID-VIEJA-RECHAZADA").first()
    vieja.created_at = datetime(2026, 6, 21, 10, 0, tzinfo=timezone.utc)

    nueva = _factura(db, p.rfc, "UUID-NUEVA-APROBADA", estado="aprobada",
                      fecha=datetime(2026, 6, 15, tzinfo=timezone.utc))
    nueva.created_at = datetime(2026, 6, 22, 9, 0, tzinfo=timezone.utc)
    db.flush()

    r = client.get("/api/v1/portal/mis-facturas", headers=_auth("profe6"),
                    params={"mes": 6, "anio": 2026, "limit": 1})
    assert r.status_code == 200
    data = r.json()
    assert data["items"][0]["uuid_cfdi"] == "UUID-NUEVA-APROBADA"
    assert data["items"][0]["estado"] == "aprobada"
