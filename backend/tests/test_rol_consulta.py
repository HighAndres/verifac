"""Pruebas del rol 'consulta': solo ve el dashboard y descarga el Excel de
reportes (facturas/export-mes) — sin acceso a ninguna otra pantalla ni permiso
de escritura en ningún lado."""
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


def _usuario(db, username, rol, profesor_id=None):
    u = Usuario(username=username, nombre=username, password_hash=hash_password("x"),
                rol=rol, profesor_id=profesor_id, activo=True)
    db.add(u)
    db.flush()
    return u


def _consulta_headers(db):
    _usuario(db, "lector", "consulta")
    return {"Authorization": f"Bearer {create_access_token('lector', 'consulta')}"}


def _admin_headers(db):
    _usuario(db, "admin_x", "superadmin")
    return {"Authorization": f"Bearer {create_access_token('admin_x', 'superadmin')}"}


def _profesor(db, rfc="CON010101AA1", nombre="Profe Consulta"):
    p = Profesor(rfc=rfc, nombre=nombre, correo="con@example.com", regimen_fiscal="612", activo=True)
    db.add(p)
    db.flush()
    return p


def test_consulta_puede_ver_dashboard_y_descargar_excel(client, db):
    headers = _consulta_headers(db)
    p = _profesor(db)
    db.add(Factura(uuid_cfdi="CON-1", rfc_emisor=p.rfc, estado="aprobada", total=1000,
                   fecha_emision=datetime(2026, 6, 10, tzinfo=timezone.utc), origen="xml"))
    db.flush()

    assert client.get("/api/v1/dashboard?mes=6&anio=2026", headers=headers).status_code == 200
    r = client.get("/api/v1/facturas/export-mes?mes=6&anio=2026", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_consulta_sin_acceso_a_profesores_facturas_pagos_catalogo(client, db):
    # 'consulta' ya no ve estas pantallas — solo dashboard + export-mes.
    headers = _consulta_headers(db)
    p = _profesor(db, rfc="CON020202BB2", nombre="Profe Consulta 2")

    assert client.get("/api/v1/profesores", headers=headers).status_code == 403
    assert client.get(f"/api/v1/profesores/{p.id}", headers=headers).status_code == 403
    assert client.get(f"/api/v1/profesores/{p.id}/claves", headers=headers).status_code == 403
    assert client.get("/api/v1/facturas", headers=headers).status_code == 403
    assert client.get("/api/v1/facturas/montos/6/2026", headers=headers).status_code == 403
    assert client.get("/api/v1/pagos?mes=6&anio=2026", headers=headers).status_code == 403
    assert client.get("/api/v1/catalogo-claves", headers=headers).status_code == 403


def test_consulta_no_puede_escribir_en_ningun_lado(client, db):
    headers = _consulta_headers(db)
    p = _profesor(db, rfc="CON030303CC3", nombre="Profe Consulta 3")

    assert client.post("/api/v1/profesores", headers=headers, json={
        "rfc": "XXX010101XX1", "nombre": "X", "correo": "x@example.com", "regimen_fiscal": "612",
    }).status_code == 403
    assert client.patch(f"/api/v1/profesores/{p.id}", headers=headers, json={"nombre": "Otro"}).status_code == 403
    assert client.delete(f"/api/v1/profesores/{p.id}", headers=headers).status_code == 403
    assert client.put("/api/v1/pagos", headers=headers, json={
        "profesor_id": str(p.id), "mes": 6, "anio": 2026, "pagada": True,
    }).status_code == 403
    assert client.post("/api/v1/facturas/upload", headers=headers,
                       files={"xml_file": ("f.xml", b"<x/>", "application/xml")}).status_code == 403
    assert client.post("/api/v1/facturas/revalidar-mes?mes=6&anio=2026", headers=headers).status_code == 403
    assert client.post("/api/v1/facturas/upload-montos", headers=headers,
                       data={"mes": "6", "anio": "2026"},
                       files={"file": ("m.xlsx", b"", "application/vnd.ms-excel")}).status_code == 403
    assert client.post("/api/v1/catalogo-claves", headers=headers, json={
        "clave": "99999999", "descripcion": "x", "tipo": "servicio",
    }).status_code == 403


def test_consulta_sin_acceso_a_watcher_usuarios_auditoria(client, db):
    headers = _consulta_headers(db)
    assert client.get("/api/v1/watcher/status", headers=headers).status_code == 403
    assert client.get("/api/v1/usuarios", headers=headers).status_code == 403
    assert client.get("/api/v1/auditoria", headers=headers).status_code == 403


def test_superadmin_puede_crear_usuario_rol_consulta(client, db):
    headers = _admin_headers(db)
    r = client.post("/api/v1/usuarios", headers=headers, json={
        "username": "nueva_consulta", "nombre": "Nueva Consulta",
        "correo": "nueva.consulta@example.com", "password": "x1234567", "rol": "consulta",
    })
    assert r.status_code == 201
    assert r.json()["rol"] == "consulta"
