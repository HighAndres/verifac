"""Reglas de coherencia rol 'profesor' ↔ profesor_id al crear/editar usuarios."""
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.profesor import Profesor
from app.models.usuario import Usuario


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers(db):
    a = Usuario(username="root", nombre="Root", password_hash=hash_password("x"),
                rol="superadmin", activo=True)
    db.add(a)
    db.flush()
    return {"Authorization": f"Bearer {create_access_token('root', 'superadmin')}"}


def _profesor(db, rfc="ZZZ090909ZZ9"):
    p = Profesor(rfc=rfc, nombre="Profe Z", correo="z@example.com", regimen_fiscal="612", activo=True)
    db.add(p)
    db.flush()
    return p


def test_crear_profesor_requiere_profesor_id(client, admin_headers):
    r = client.post("/api/v1/usuarios", headers=admin_headers, json={
        "username": "p1", "nombre": "P1", "password": "secreto", "rol": "profesor",
    })
    assert r.status_code == 422


def test_crear_profesor_liga_ok(client, admin_headers, db):
    p = _profesor(db)
    r = client.post("/api/v1/usuarios", headers=admin_headers, json={
        "username": "p2", "nombre": "P2", "password": "secreto",
        "rol": "profesor", "profesor_id": str(p.id),
    })
    assert r.status_code == 201
    assert r.json()["profesor_id"] == str(p.id)


def test_no_dos_usuarios_al_mismo_profesor(client, admin_headers, db):
    p = _profesor(db, rfc="YYY080808YY8")
    db.add(Usuario(username="ya", nombre="Ya", password_hash=hash_password("x"),
                   rol="profesor", profesor_id=p.id, activo=True))
    db.flush()
    r = client.post("/api/v1/usuarios", headers=admin_headers, json={
        "username": "otro", "nombre": "Otro", "password": "secreto",
        "rol": "profesor", "profesor_id": str(p.id),
    })
    assert r.status_code == 409


def test_rol_no_profesor_limpia_profesor_id(client, admin_headers, db):
    r = client.post("/api/v1/usuarios", headers=admin_headers, json={
        "username": "rev", "nombre": "Rev", "password": "secreto",
        "rol": "revisor", "profesor_id": str(_profesor(db, rfc="WWW070707WW7").id),
    })
    assert r.status_code == 201
    assert r.json()["profesor_id"] is None
