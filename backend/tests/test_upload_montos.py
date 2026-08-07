"""Pruebas de POST /api/v1/facturas/upload-montos (carga del layout de montos)."""
import io

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.monto_mensual import MontoMensual
from app.models.usuario import Usuario

CABECERA = ["Categoría", "Clave régimen emisor", "Nombre emisor",
            "Subtotal", "IVA Trasladado", "IVA Retenido", "ISR retenido", "Total"]


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


def _xlsx(filas: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(CABECERA)
    for f in filas:
        ws.append(f)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_upload_montos_rechaza_regimen_con_punto_decimal(client, db):
    headers = _rev_headers(db)
    # Simula el caso real: Excel/Sheets exporta la columna de régimen como número
    # decimal (626.0) en vez de texto, lo que rebasa el VARCHAR(3) de la BD.
    data = _xlsx([["Música", "626.0", "JUAN PEREZ LOPEZ", 1000, 160, 106.67, 100, 953.33]])
    res = client.post(
        "/api/v1/facturas/upload-montos",
        params={"mes": 6, "anio": 2026},
        files={"file": ("montos.xlsx", data,
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert res.status_code == 422, res.text
    assert "Régimen fiscal inválido" in res.json()["detail"]
    assert db.query(MontoMensual).filter(MontoMensual.nombre_layout == "JUAN PEREZ LOPEZ").count() == 0


def test_upload_montos_acepta_regimen_valido(client, db):
    headers = _rev_headers(db)
    data = _xlsx([["Música", "626", "JUAN PEREZ LOPEZ", 1000, 160, 106.67, 100, 953.33]])
    res = client.post(
        "/api/v1/facturas/upload-montos",
        params={"mes": 6, "anio": 2026},
        files={"file": ("montos.xlsx", data,
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert db.query(MontoMensual).filter(
        MontoMensual.nombre_layout == "JUAN PEREZ LOPEZ",
        MontoMensual.regimen_fiscal == "626",
    ).count() == 1
