"""Editar usuarios no debe exigir recapturar el correo: un correo idéntico al
actual (o ausente en el payload) no se revalida, para que cambiar contraseña u
otros campos funcione aunque el usuario tenga correo placeholder o None."""
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.main import app
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


def _usuario(db, username, correo):
    u = Usuario(username=username, nombre=username.title(),
                password_hash=hash_password("vieja"), correo=correo,
                rol="revisor", activo=True)
    db.add(u)
    db.flush()
    return u


def test_cambiar_password_sin_correo(client, admin_headers, db):
    u = _usuario(db, "sincorreo", None)
    r = client.patch(f"/api/v1/usuarios/{u.id}", headers=admin_headers,
                     json={"password": "nueva123"})
    assert r.status_code == 200
    assert verify_password("nueva123", u.password_hash)


def test_editar_con_correo_placeholder_sin_cambiarlo(client, admin_headers, db):
    u = _usuario(db, "placeholder", "abc010101abc@pendiente.local")
    r = client.patch(f"/api/v1/usuarios/{u.id}", headers=admin_headers,
                     json={"nombre": "Nuevo Nombre", "correo": "abc010101abc@pendiente.local",
                           "password": "nueva123"})
    assert r.status_code == 200
    assert r.json()["nombre"] == "Nuevo Nombre"
    assert verify_password("nueva123", u.password_hash)


def test_correo_igual_al_actual_no_choca_con_unicidad(client, admin_headers, db):
    u = _usuario(db, "mismo", "mismo@example.com")
    r = client.patch(f"/api/v1/usuarios/{u.id}", headers=admin_headers,
                     json={"correo": "MISMO@example.com", "nombre": "Igual"})
    assert r.status_code == 200


def test_cambiar_a_placeholder_sigue_rechazado(client, admin_headers, db):
    u = _usuario(db, "valido", "valido@example.com")
    r = client.patch(f"/api/v1/usuarios/{u.id}", headers=admin_headers,
                     json={"correo": "otro@pendiente.local"})
    assert r.status_code == 422


def test_quitar_correo_sigue_rechazado(client, admin_headers, db):
    u = _usuario(db, "concorreo", "concorreo@example.com")
    r = client.patch(f"/api/v1/usuarios/{u.id}", headers=admin_headers,
                     json={"correo": None})
    assert r.status_code == 422
