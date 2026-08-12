"""Login por CORREO (no por username). Ver [[project-reglas-negocio]]."""
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.security import hash_password
from app.main import app
from app.models.usuario import Usuario


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _crear(db, username, correo, password="secreto", rol="revisor", activo=True):
    # Idempotente: el login hace commit (ultimo_acceso) y escapa el rollback del
    # test, así que en reruns el usuario puede seguir ahí. Se reutiliza si existe.
    u = db.query(Usuario).filter(Usuario.username == username).first()
    if u is None:
        u = Usuario(username=username, nombre=username, correo=correo,
                    password_hash=hash_password(password), rol=rol, activo=activo)
        db.add(u)
    else:
        u.correo, u.password_hash, u.rol, u.activo = correo, hash_password(password), rol, activo
    db.flush()
    return u


def _login(client, correo, password="secreto"):
    # El campo del formulario OAuth2 se llama "username" pero lleva el correo.
    return client.post("/api/v1/auth/login", data={"username": correo, "password": password})


def test_login_por_correo_ok(client, db):
    _crear(db, "jperez", "juan.perez@thehumantalent.com")
    r = _login(client, "juan.perez@thehumantalent.com")
    assert r.status_code == 200, r.text
    assert r.json()["rol"] == "revisor"


def test_login_correo_case_insensitive(client, db):
    _crear(db, "jperez2", "juan.perez2@thehumantalent.com")
    r = _login(client, "  Juan.Perez2@TheHumanTalent.com ")
    assert r.status_code == 200, r.text


def test_login_password_incorrecto(client, db):
    _crear(db, "jperez3", "juan.perez3@thehumantalent.com")
    r = _login(client, "juan.perez3@thehumantalent.com", password="malo")
    assert r.status_code == 401


def test_login_correo_inexistente(client, db):
    r = _login(client, "nadie@thehumantalent.com")
    assert r.status_code == 401


def test_login_no_permite_username(client, db):
    """Ya no se entra por username: usarlo como credencial falla."""
    _crear(db, "solo_username", "solo.username@thehumantalent.com")
    r = _login(client, "solo_username")
    assert r.status_code == 401


def test_login_rechaza_placeholder(client, db):
    """Un correo placeholder no es credencial válida aunque exista en la BD."""
    _crear(db, "profe_x", "abc123@pendiente.local")
    r = _login(client, "abc123@pendiente.local")
    assert r.status_code == 401


def test_login_usuario_inactivo(client, db):
    _crear(db, "inactivo", "inactivo@thehumantalent.com", activo=False)
    r = _login(client, "inactivo@thehumantalent.com")
    assert r.status_code == 401
