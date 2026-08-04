"""Pruebas de POST /api/v1/catalogo-claves/lote (alta de claves SAT en lote)."""
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.catalogo_clave import CatalogoClave
from app.models.usuario import Usuario


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _rev_headers(db):
    u = Usuario(username="rev", nombre="rev", password_hash=hash_password("x"), rol="revisor", activo=True)
    db.add(u)
    db.flush()
    return {"Authorization": f"Bearer {create_access_token('rev', 'revisor')}"}


def test_lote_crea_evita_duplicados_y_reporta_errores(client, db):
    headers = _rev_headers(db)
    db.add(CatalogoClave(clave="TESTLOTE01", descripcion="ya existía", tipo="servicio", activo=True))
    db.flush()

    payload = {"items": [
        {"clave": "TESTLOTE02", "descripcion": "Servicios de enseñanza", "tipo": "servicio", "activo": True},
        {"clave": "TESTLOTE01", "descripcion": "duplicada contra BD", "tipo": "servicio", "activo": True},
        {"clave": "TESTLOTE02", "descripcion": "duplicada dentro del mismo lote", "tipo": "servicio", "activo": True},
        {"clave": "TESTLOTE03", "descripcion": "Unidad de servicio", "tipo": "unidad", "activo": True},
        {"clave": "TESTLOTE04", "descripcion": "tipo invalido", "tipo": "otro", "activo": True},
    ]}
    res = client.post("/api/v1/catalogo-claves/lote", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["creadas"] == 2, data
    assert data["existentes"] == 2, data
    assert len(data["errores"]) == 1, data

    nuevas = {c.clave for c in db.query(CatalogoClave).filter(CatalogoClave.clave.like("TESTLOTE%")).all()}
    assert nuevas == {"TESTLOTE01", "TESTLOTE02", "TESTLOTE03"}


def test_lote_rechaza_clave_con_punto_decimal(client, db):
    headers = _rev_headers(db)
    payload = {"items": [
        {"clave": "86131600.0", "descripcion": "Música y drama", "tipo": "servicio", "activo": True},
    ]}
    res = client.post("/api/v1/catalogo-claves/lote", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["creadas"] == 0 and len(data["errores"]) == 1
    assert "punto decimal" in data["errores"][0]
    assert db.query(CatalogoClave).filter(CatalogoClave.clave == "86131600.0").first() is None


def test_crear_clave_individual_rechaza_punto_decimal(client, db):
    headers = _rev_headers(db)
    payload = {"clave": "90141702.0", "descripcion": "Ligas deportivas", "tipo": "servicio", "activo": True}
    res = client.post("/api/v1/catalogo-claves", json=payload, headers=headers)
    assert res.status_code == 422, res.text
    assert "punto decimal" in res.json()["detail"]
