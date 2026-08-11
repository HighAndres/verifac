"""Pruebas de POST /api/v1/facturas/upload-montos (carga del layout de montos)."""
import io
from datetime import datetime
from zoneinfo import ZoneInfo

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


def _asegurar_usuario(db, username: str, rol: str):
    """Crea el usuario si no existe (los endpoints hacen commit, así que puede
    haber quedado de una corrida previa; reutilizarlo mantiene los tests idempotentes)."""
    u = db.query(Usuario).filter(Usuario.username == username).first()
    if u is None:
        u = Usuario(username=username, nombre=username, password_hash=hash_password("x"),
                    rol=rol, activo=True)
        db.add(u)
        db.flush()
    return {"Authorization": f"Bearer {create_access_token(username, rol)}"}


def _rev_headers(db):
    return _asegurar_usuario(db, "rev", "revisor")


def _admin_headers(db):
    return _asegurar_usuario(db, "admin", "superadmin")


def _xlsx(filas: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(CABECERA)
    for f in filas:
        ws.append(f)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# El layout solo se puede cargar en el mes en curso (hora de México).
_HOY_MX = datetime.now(ZoneInfo("America/Mexico_City"))
MES_ACTUAL, ANIO_ACTUAL = _HOY_MX.month, _HOY_MX.year


def test_upload_montos_rechaza_regimen_con_punto_decimal(client, db):
    headers = _rev_headers(db)
    # Simula el caso real: Excel/Sheets exporta la columna de régimen como número
    # decimal (626.0) en vez de texto, lo que rebasa el VARCHAR(3) de la BD.
    data = _xlsx([["Música", "626.0", "JUAN PEREZ LOPEZ", 1000, 160, 106.67, 100, 953.33]])
    res = client.post(
        "/api/v1/facturas/upload-montos",
        params={"mes": MES_ACTUAL, "anio": ANIO_ACTUAL},
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
        params={"mes": MES_ACTUAL, "anio": ANIO_ACTUAL},
        files={"file": ("montos.xlsx", data,
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert db.query(MontoMensual).filter(
        MontoMensual.nombre_layout == "JUAN PEREZ LOPEZ",
        MontoMensual.regimen_fiscal == "626",
    ).count() == 1


def test_upload_montos_revisor_rechaza_mes_distinto_al_actual(client, db):
    """El revisor solo puede cargar el layout del mes en curso; otro periodo → 422."""
    headers = _rev_headers(db)
    # Un mes que nunca es el actual: si hoy es enero usamos febrero, si no enero.
    mes_otro = 2 if MES_ACTUAL == 1 else 1
    data = _xlsx([["Música", "626", "JUAN PEREZ LOPEZ", 1000, 160, 106.67, 100, 953.33]])
    res = client.post(
        "/api/v1/facturas/upload-montos",
        params={"mes": mes_otro, "anio": ANIO_ACTUAL},
        files={"file": ("montos.xlsx", data,
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert res.status_code == 422, res.text
    assert "mes en curso" in res.json()["detail"]
    assert db.query(MontoMensual).filter(
        MontoMensual.nombre_layout == "JUAN PEREZ LOPEZ",
    ).count() == 0


def test_upload_montos_revisor_rechaza_anio_distinto_al_actual(client, db):
    """Revisor: mismo mes pero año pasado también se rechaza."""
    headers = _rev_headers(db)
    data = _xlsx([["Música", "626", "JUAN PEREZ LOPEZ", 1000, 160, 106.67, 100, 953.33]])
    res = client.post(
        "/api/v1/facturas/upload-montos",
        params={"mes": MES_ACTUAL, "anio": ANIO_ACTUAL - 1},
        files={"file": ("montos.xlsx", data,
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert res.status_code == 422, res.text
    assert "mes en curso" in res.json()["detail"]


def test_upload_montos_superadmin_permite_mes_distinto_al_actual(client, db):
    """El superadmin sí puede cargar el layout de un periodo distinto al mes en curso."""
    headers = _admin_headers(db)
    mes_otro = 2 if MES_ACTUAL == 1 else 1
    data = _xlsx([["Música", "626", "JUAN PEREZ LOPEZ", 1000, 160, 106.67, 100, 953.33]])
    res = client.post(
        "/api/v1/facturas/upload-montos",
        params={"mes": mes_otro, "anio": ANIO_ACTUAL - 1},
        files={"file": ("montos.xlsx", data,
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert db.query(MontoMensual).filter(
        MontoMensual.nombre_layout == "JUAN PEREZ LOPEZ",
        MontoMensual.mes == mes_otro,
        MontoMensual.anio == ANIO_ACTUAL - 1,
    ).count() == 1
