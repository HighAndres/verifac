"""Generación masiva de cuentas de profesores y envío de credenciales por correo,
más el reenvío individual (regenera la contraseña y la manda al correo).

Las pruebas corren contra la BD de desarrollo (puede tener profesores sembrados),
así que las aserciones del lote son por RFC propio, no por totales absolutos.
"""
import re

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.main import app
from app.models.profesor import Profesor
from app.models.usuario import Usuario
from app.services import credenciales as cred


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def correo_ok(monkeypatch):
    """SMTP "configurado" y capturado: no se envía nada real."""
    enviados = []
    monkeypatch.setattr(cred, "enviar_smtp",
                        lambda dest, asunto, cuerpo: enviados.append((dest, asunto, cuerpo)))
    monkeypatch.setattr("app.api.v1.endpoints.usuarios.password_configurado", lambda: True)
    return enviados


def _admin_headers(db):
    db.add(Usuario(username="admin_cred", nombre="admin", password_hash=hash_password("x"),
                   rol="superadmin", activo=True))
    db.flush()
    return {"Authorization": f"Bearer {create_access_token('admin_cred', 'superadmin')}"}


def _profesor(db, rfc, nombre, correo, activo=True):
    p = Profesor(rfc=rfc, nombre=nombre, correo=correo, regimen_fiscal="612", activo=activo)
    db.add(p)
    db.flush()
    return p


def _password_del_correo(cuerpo: str) -> str:
    m = re.search(r"Contraseña:\s+(\S+)", cuerpo)
    assert m, cuerpo
    return m.group(1)


def test_generacion_masiva_crea_cuentas_y_envia(client, db, correo_ok):
    headers = _admin_headers(db)
    sin_cuenta = _profesor(db, "CRE010101AA1", "Profe Nuevo", "nuevo@example.com")
    _profesor(db, "CRE010101AA2", "Profe Placeholder", "cre010101aa2@pendiente.local")
    con_cuenta = _profesor(db, "CRE010101AA3", "Profe Con Cuenta", "concuenta@example.com")
    db.add(Usuario(username="ya_tiene", nombre="Profe Con Cuenta", correo="concuenta@example.com",
                   password_hash=hash_password("x"), rol="profesor", profesor_id=con_cuenta.id))
    _profesor(db, "CRE010101AA4", "Profe Inactivo", "inactivo@example.com", activo=False)
    sin_cuenta_id = sin_cuenta.id
    con_cuenta_id = con_cuenta.id
    db.commit()   # el endpoint comitea por profesor; el setup debe sobrevivir eso

    r = client.post("/api/v1/usuarios/generar-credenciales-profesores", headers=headers)
    assert r.status_code == 200
    data = r.json()

    rfcs_creados = {d["rfc"] for d in data["detalle_creados"]}
    rfcs_omitidos = {d["rfc"] for d in data["detalle_omitidos"]}
    assert "CRE010101AA1" in rfcs_creados
    assert "CRE010101AA2" in rfcs_omitidos          # placeholder: sin correo real
    assert "CRE010101AA3" not in rfcs_creados        # ya tenía cuenta
    assert "CRE010101AA4" not in rfcs_creados | rfcs_omitidos   # inactivo

    # La cuenta quedó ligada al profesor y la contraseña enviada funciona.
    user = db.query(Usuario).filter(Usuario.profesor_id == sin_cuenta_id).first()
    assert user is not None and user.rol == "profesor"
    assert user.correo == "nuevo@example.com"
    nuestro = [e for e in correo_ok if e[0] == "nuevo@example.com"]
    assert len(nuestro) == 1
    assert verify_password(_password_del_correo(nuestro[0][2]), user.password_hash)

    # No se creó una segunda cuenta para el que ya tenía.
    assert db.query(Usuario).filter(Usuario.profesor_id == con_cuenta_id).count() == 1


def test_generacion_masiva_revierte_cuenta_si_el_envio_falla(client, db, correo_ok, monkeypatch):
    headers = _admin_headers(db)
    p = _profesor(db, "CRE020202BB1", "Profe Falla", "falla@example.com")
    p_id = p.id
    db.commit()

    def _truena(dest, asunto, cuerpo):
        raise ConnectionError("smtp caído")
    monkeypatch.setattr(cred, "enviar_smtp", _truena)

    r = client.post("/api/v1/usuarios/generar-credenciales-profesores", headers=headers)
    assert r.status_code == 200
    data = r.json()
    # Un fallo de conexión corta el lote: nada se crea y hay exactamente un error.
    assert data["creados"] == 0
    assert data["errores"] == 1
    # Sin cuenta a medias: nadie conoce esa contraseña.
    assert db.query(Usuario).filter(Usuario.profesor_id == p_id).first() is None


def test_reenvio_individual_regenera_password(client, db, correo_ok):
    headers = _admin_headers(db)
    user = Usuario(username="profe_re", nombre="Profe Re", correo="re@example.com",
                   password_hash=hash_password("vieja"), rol="profesor")
    db.add(user)
    db.commit()

    r = client.post(f"/api/v1/usuarios/{user.id}/enviar-credenciales", headers=headers)
    assert r.status_code == 200
    assert r.json()["enviado_a"] == "re@example.com"
    db.refresh(user)
    assert not verify_password("vieja", user.password_hash)
    assert verify_password(_password_del_correo(correo_ok[-1][2]), user.password_hash)


def test_reenvio_individual_falla_conserva_password(client, db, correo_ok, monkeypatch):
    headers = _admin_headers(db)
    user = Usuario(username="profe_re2", nombre="Profe Re2", correo="re2@example.com",
                   password_hash=hash_password("vieja"), rol="profesor")
    db.add(user)
    db.commit()

    def _truena(dest, asunto, cuerpo):
        raise ConnectionError("smtp caído")
    monkeypatch.setattr(cred, "enviar_smtp", _truena)

    r = client.post(f"/api/v1/usuarios/{user.id}/enviar-credenciales", headers=headers)
    assert r.status_code == 502
    db.refresh(user)
    assert verify_password("vieja", user.password_hash)


def test_reenvio_a_cuenta_sin_correo_real_422(client, db, correo_ok):
    headers = _admin_headers(db)
    user = Usuario(username="profe_ph", nombre="Profe PH", correo="x@pendiente.local",
                   password_hash=hash_password("vieja"), rol="profesor")
    db.add(user)
    db.commit()
    r = client.post(f"/api/v1/usuarios/{user.id}/enviar-credenciales", headers=headers)
    assert r.status_code == 422


def test_sin_correo_configurado_422(client, db, monkeypatch):
    headers = _admin_headers(db)
    monkeypatch.setattr("app.api.v1.endpoints.usuarios.password_configurado", lambda: False)
    r = client.post("/api/v1/usuarios/generar-credenciales-profesores", headers=headers)
    assert r.status_code == 422
