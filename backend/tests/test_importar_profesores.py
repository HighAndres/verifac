"""Pruebas de la importación masiva de profesores desde Excel."""
import io

import openpyxl

from app.models.catalogo_clave import CatalogoClave
from app.models.monto_mensual import MontoMensual
from app.models.profesor import Profesor
from app.models.profesor_clave import ProfesorClave
from app.services.import_profesores import importar_profesores

CABECERA = ["Nombre", "RFC", "Correo", "Clave régimen emisor", "Clave prod/serv", "Concepto de servicio"]


def _xlsx(filas: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(CABECERA)
    for f in filas:
        ws.append(f)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_crea_profesor_con_clave_y_autocatalogo(db):
    # Clave inusual para asegurar que se crea nueva en el catálogo.
    data = _xlsx([["JUAN PEREZ LOPEZ", "PELJ850101AA1", "juan@correo.com", "612", "99999901", "Servicio de prueba"]])
    res = importar_profesores(data, db)
    assert res.creados == 1
    prof = db.query(Profesor).filter(Profesor.rfc == "PELJ850101AA1").first()
    assert prof and prof.correo == "juan@correo.com" and prof.regimen_fiscal == "612"
    cat = db.query(CatalogoClave).filter(CatalogoClave.clave == "99999901").first()
    assert cat and cat.tipo == "servicio"
    assert res.claves_nuevas_catalogo == 1 and res.claves_asignadas == 1
    assert db.query(ProfesorClave).filter(ProfesorClave.profesor_id == prof.id).count() == 1


def test_correo_placeholder_cuando_falta(db):
    data = _xlsx([["ANA GOMEZ RUIZ", "GORA900202BB2", "", "626", "", ""]])
    res = importar_profesores(data, db)
    assert res.creados == 1
    prof = db.query(Profesor).filter(Profesor.rfc == "GORA900202BB2").first()
    assert prof.correo == "gora900202bb2@pendiente.local"


def test_actualiza_por_rfc_sin_pisar_correo_real(db):
    db.add(Profesor(rfc="ROBL880303CC3", nombre="ROBERTO L", correo="real@correo.com",
                    regimen_fiscal="612", activo=True))
    db.flush()
    # Sin correo en el archivo → no debe pisar el real; sí actualiza nombre/régimen
    data = _xlsx([["ROBERTO LARA", "ROBL880303CC3", "", "626", "", ""]])
    res = importar_profesores(data, db)
    assert res.creados == 0 and res.actualizados == 1
    prof = db.query(Profesor).filter(Profesor.rfc == "ROBL880303CC3").first()
    assert prof.correo == "real@correo.com"
    assert prof.nombre == "ROBERTO LARA" and prof.regimen_fiscal == "626"


def test_reenlaza_montos_sueltos(db):
    db.add(MontoMensual(profesor_id=None, nombre_layout="LUIS MENDEZ", rfc_emisor="MELU870404DD4",
                        regimen_fiscal="612", mes=7, anio=2026, subtotal=1000, iva_trasladado=160,
                        iva_retenido=106.67, isr_retenido=100, total=953.33))
    db.flush()
    data = _xlsx([["LUIS MENDEZ", "MELU870404DD4", "luis@correo.com", "612", "", ""]])
    res = importar_profesores(data, db)
    assert res.montos_reenlazados >= 1
    prof = db.query(Profesor).filter(Profesor.rfc == "MELU870404DD4").first()
    m = db.query(MontoMensual).filter(MontoMensual.rfc_emisor == "MELU870404DD4").first()
    assert m.profesor_id == prof.id


def test_rfc_invalido_reporta_error(db):
    data = _xlsx([["MAL RFC", "XXX", "x@correo.com", "612", "", ""]])
    res = importar_profesores(data, db)
    assert res.creados == 0 and len(res.errores) == 1
    assert res.errores[0]["fila"] == 2


def test_clave_serv_con_punto_decimal_reporta_error(db):
    # Simula el caso real: Excel/Sheets exporta la columna de clave como número
    # decimal (86131600.0) en vez de texto.
    data = _xlsx([["JUAN PEREZ LOPEZ", "PELJ850101AA1", "juan@correo.com", "612", "86131600.0", "Música y drama"]])
    res = importar_profesores(data, db)
    assert res.creados == 0 and len(res.errores) == 1
    assert "punto decimal" in res.errores[0]["motivo"]
    assert db.query(CatalogoClave).filter(CatalogoClave.clave == "86131600.0").first() is None
    assert db.query(Profesor).filter(Profesor.rfc == "PELJ850101AA1").first() is None


def test_falta_columna_obligatoria(db):
    import pytest
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Nombre", "Correo"])   # sin RFC ni Régimen
    ws.append(["ALGUIEN", "a@b.com"])
    buf = io.BytesIO(); wb.save(buf)
    with pytest.raises(ValueError):
        importar_profesores(buf.getvalue(), db)
