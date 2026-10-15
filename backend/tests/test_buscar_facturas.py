"""Búsqueda `q` en el listado de facturas (nombre del emisor o RFC, contiene).
La caja de búsqueda del frontend siempre mandó `q`; antes el backend lo ignoraba."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.factura import Factura
from app.models.usuario import Usuario


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _headers(db):
    db.add(Usuario(username="rev_q", nombre="rev", password_hash=hash_password("x"),
                   rol="revisor", activo=True))
    db.flush()
    return {"Authorization": f"Bearer {create_access_token('rev_q', 'revisor')}"}


def _factura(db, uuid_cfdi, rfc, nombre):
    db.add(Factura(uuid_cfdi=uuid_cfdi, rfc_emisor=rfc, nombre_emisor=nombre,
                   estado="aprobada", total=100, origen="xml",
                   fecha_emision=datetime(2099, 5, 10, tzinfo=timezone.utc)))
    db.flush()


def test_busca_por_nombre_y_por_rfc(client, db):
    headers = _headers(db)
    _factura(db, "Q-1", "QQQ010101AA1", "MARIA BUSCABLE LOPEZ")
    _factura(db, "Q-2", "QQQ010101BB2", "OTRO EMISOR")

    r = client.get("/api/v1/facturas?anio=2099&q=buscable", headers=headers)
    assert r.status_code == 200
    assert [f["uuid_cfdi"] for f in r.json()["items"]] == ["Q-1"]

    r = client.get("/api/v1/facturas?anio=2099&q=QQQ010101BB", headers=headers)
    assert [f["uuid_cfdi"] for f in r.json()["items"]] == ["Q-2"]

    r = client.get("/api/v1/facturas?anio=2099&q=QQQ010101", headers=headers)
    assert r.json()["total"] == 2
