"""Pruebas del interruptor global "carga de XML del portal" (superadmin)."""
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


def _usuario(db, username, rol, profesor_id=None):
    u = Usuario(username=username, nombre=username, password_hash=hash_password("x"),
                rol=rol, profesor_id=profesor_id, activo=True)
    db.add(u)
    db.flush()
    return u


def _admin_headers(db):
    _usuario(db, "admin_cxml", "superadmin")
    return {"Authorization": f"Bearer {create_access_token('admin_cxml', 'superadmin')}"}


def _revisor_headers(db):
    _usuario(db, "rev_cxml", "revisor")
    return {"Authorization": f"Bearer {create_access_token('rev_cxml', 'revisor')}"}


def _profesor_con_cuenta(db, username="profe_cxml"):
    p = Profesor(rfc="CXM010101AA1", nombre="Profe Carga XML", correo="cxml@example.com",
                 regimen_fiscal="612", activo=True)
    db.add(p)
    db.flush()
    _usuario(db, username, "profesor", profesor_id=p.id)
    return p, {"Authorization": f"Bearer {create_access_token(username, 'profesor')}"}


def test_por_defecto_esta_activa(client, db):
    headers = _admin_headers(db)
    r = client.get("/api/v1/configuracion/carga-xml", headers=headers)
    assert r.status_code == 200
    assert r.json()["carga_xml_portal_activa"] is True


def test_solo_superadmin_puede_leer_o_cambiar(client, db):
    rev_headers = _revisor_headers(db)
    assert client.get("/api/v1/configuracion/carga-xml", headers=rev_headers).status_code == 403
    assert client.put("/api/v1/configuracion/carga-xml", headers=rev_headers,
                      json={"carga_xml_portal_activa": False}).status_code == 403


def test_apagar_bloquea_subida_del_portal_y_prender_la_restaura(client, db):
    admin_headers = _admin_headers(db)
    profesor, profe_headers = _profesor_con_cuenta(db)

    # Se ve en mi-perfil que está activa.
    perfil = client.get("/api/v1/portal/mi-perfil", headers=profe_headers).json()
    assert perfil["carga_xml_activa"] is True

    # El superadmin la apaga.
    r = client.put("/api/v1/configuracion/carga-xml", headers=admin_headers,
                   json={"carga_xml_portal_activa": False})
    assert r.status_code == 200
    assert r.json()["carga_xml_portal_activa"] is False

    # mi-perfil ya refleja el apagado.
    perfil2 = client.get("/api/v1/portal/mi-perfil", headers=profe_headers).json()
    assert perfil2["carga_xml_activa"] is False

    # La subida se rechaza con 423, sin importar el contenido del archivo.
    r2 = client.post("/api/v1/portal/subir-factura", headers=profe_headers,
                     files={"xml": ("f.xml", b"<cualquier/>", "application/xml")})
    assert r2.status_code == 423

    # El superadmin la vuelve a prender.
    r3 = client.put("/api/v1/configuracion/carga-xml", headers=admin_headers,
                    json={"carga_xml_portal_activa": True})
    assert r3.status_code == 200
    assert r3.json()["carga_xml_portal_activa"] is True


def test_cambio_queda_en_bitacora(client, db):
    admin_headers = _admin_headers(db)
    client.put("/api/v1/configuracion/carga-xml", headers=admin_headers,
              json={"carga_xml_portal_activa": False})

    r = client.get("/api/v1/auditoria?recurso=configuracion_app", headers=admin_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert items[0]["username"] == "admin_cxml"
    assert "desactivada" in items[0]["detalle"]
