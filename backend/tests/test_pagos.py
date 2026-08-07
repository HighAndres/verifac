"""Pruebas de la pantalla de Pagos y el portal mis-pagos."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.factura import Factura
from app.models.pago import Pago
from app.models.profesor import Profesor
from app.models.usuario import Usuario


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _profesor(db, rfc, nombre, correo, activo=True):
    p = Profesor(rfc=rfc, nombre=nombre, correo=correo, regimen_fiscal="612", activo=activo)
    db.add(p)
    db.flush()
    return p


def _usuario(db, username, rol, profesor_id=None):
    u = Usuario(username=username, nombre=username, password_hash=hash_password("x"),
                rol=rol, profesor_id=profesor_id, activo=True)
    db.add(u)
    db.flush()
    return u


def _rev_headers(db):
    _usuario(db, "rev", "revisor")
    return {"Authorization": f"Bearer {create_access_token('rev', 'revisor')}"}


def _prof_headers(username):
    return {"Authorization": f"Bearer {create_access_token(username, 'profesor')}"}


def test_put_pagos_crea_y_actualiza(client, db):
    headers = _rev_headers(db)
    p = _profesor(db, "AAA010101AA1", "Profe A", "a@example.com")

    # Crear
    r = client.put("/api/v1/pagos", headers=headers, json={
        "profesor_id": str(p.id), "mes": 6, "anio": 2026,
        "pagada": True, "fecha_pago": "2026-06-30", "metodo_pago": "Transferencia",
    })
    assert r.status_code == 200
    assert r.json()["pagada"] is True
    assert r.json()["registrado_por"] == "rev"

    # Actualizar el mismo periodo (idempotente por unique) — desmarcar limpia detalles
    r2 = client.put("/api/v1/pagos", headers=headers, json={
        "profesor_id": str(p.id), "mes": 6, "anio": 2026, "pagada": False,
    })
    assert r2.status_code == 200
    assert r2.json()["pagada"] is False
    assert r2.json()["fecha_pago"] is None
    assert db.query(Pago).filter(Pago.profesor_id == p.id, Pago.mes == 6, Pago.anio == 2026).count() == 1


def test_get_pagos_lista_incluye_inactivos(client, db):
    # Se listan TODOS los profesores del catálogo (activos e inactivos), igual que
    # la pantalla de Profesores, para no ocultar a nadie silenciosamente.
    headers = _rev_headers(db)
    p1 = _profesor(db, "BBB020202BB2", "Profe B", "b@example.com")
    _profesor(db, "CCC030303CC3", "Profe C", "c@example.com")
    _profesor(db, "DDD040404DD4", "Profe D", "d@example.com", activo=False)  # inactivo: sigue apareciendo
    # factura de contexto para p1
    db.add(Factura(uuid_cfdi="U-B-1", rfc_emisor=p1.rfc, estado="aprobada", total=1234,
                   fecha_emision=datetime(2026, 6, 10, tzinfo=timezone.utc), origen="xml"))
    db.flush()

    r = client.get("/api/v1/pagos?mes=6&anio=2026", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    nombres = {i["nombre"] for i in items}
    assert {"Profe B", "Profe C", "Profe D"} <= nombres   # activos e inactivos aparecen
    fila_b = next(i for i in items if i["nombre"] == "Profe B")
    assert fila_b["factura_estado"] == "aprobada"
    assert fila_b["factura_total"] == 1234.0
    assert fila_b["pagada"] is False
    fila_d = next(i for i in items if i["nombre"] == "Profe D")
    assert fila_d["activo"] is False


def test_portal_mis_pagos_solo_propios_y_pagados(client, db):
    p1 = _profesor(db, "EEE050505EE5", "Profe E", "e@example.com")
    p2 = _profesor(db, "FFF060606FF6", "Profe F", "f@example.com")
    _usuario(db, "profe_e", "profesor", p1.id)
    db.add(Pago(profesor_id=p1.id, mes=5, anio=2026, pagada=True, metodo_pago="Cheque"))
    db.add(Pago(profesor_id=p1.id, mes=6, anio=2026, pagada=False))  # no pagado: no aparece
    db.add(Pago(profesor_id=p2.id, mes=5, anio=2026, pagada=True))   # de otro profesor
    db.flush()

    r = client.get("/api/v1/portal/mis-pagos", headers=_prof_headers("profe_e"))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["mes"] == 5 and items[0]["metodo_pago"] == "Cheque"


def test_incidencia_es_independiente_de_pagada(client, db):
    headers = _rev_headers(db)
    p = _profesor(db, "HHH080808HH8", "Profe H", "h@example.com")

    # Se puede registrar una incidencia sin marcar como pagada.
    r = client.put("/api/v1/pagos", headers=headers, json={
        "profesor_id": str(p.id), "mes": 6, "anio": 2026,
        "pagada": False, "incidencia": "Trámite en SAT",
    })
    assert r.status_code == 200
    assert r.json()["pagada"] is False
    assert r.json()["incidencia"] == "Trámite en SAT"

    # Marcar como pagada no borra la incidencia (son independientes).
    r2 = client.put("/api/v1/pagos", headers=headers, json={
        "profesor_id": str(p.id), "mes": 6, "anio": 2026,
        "pagada": True, "fecha_pago": "2026-06-30", "metodo_pago": "Transferencia",
        "incidencia": "Trámite en SAT",
    })
    assert r2.status_code == 200
    assert r2.json()["pagada"] is True
    assert r2.json()["incidencia"] == "Trámite en SAT"

    # Valor fuera del catálogo se rechaza.
    r3 = client.put("/api/v1/pagos", headers=headers, json={
        "profesor_id": str(p.id), "mes": 6, "anio": 2026,
        "pagada": False, "incidencia": "Motivo inventado",
    })
    assert r3.status_code == 422


def test_profesor_no_puede_marcar_pagos(client, db):
    p = _profesor(db, "GGG070707GG7", "Profe G", "g@example.com")
    _usuario(db, "profe_g", "profesor", p.id)
    r = client.put("/api/v1/pagos", headers=_prof_headers("profe_g"), json={
        "profesor_id": str(p.id), "mes": 6, "anio": 2026, "pagada": True,
    })
    assert r.status_code == 403
