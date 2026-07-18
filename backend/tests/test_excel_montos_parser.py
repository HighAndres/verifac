"""Pruebas del parser del layout de montos (detección de RFC/Mes/Año)."""
import io

import openpyxl

from app.services.excel_montos_parser import parsear_excel_montos

HEADER = ["Categoría", "Clave régimen emisor", "Nombre emisor", "Subtotal",
          "IVA Trasladado", "IVA Retenido", "ISR retenido", "Total", "RFC", "Mes", "Año"]


def _xlsx(rows, header=HEADER) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_detecta_rfc_mes_anio_numerico():
    data = _xlsx([["Hon", "612", "JUAN PEREZ", 1000, 160, 106.67, 100, 953.33, "PEXJ800101ABC", 6, 2026]])
    filas = parsear_excel_montos(data)
    assert len(filas) == 1
    f = filas[0]
    assert f.rfc_emisor == "PEXJ800101ABC"
    assert f.mes == 6
    assert f.anio == 2026


def test_mes_por_nombre():
    data = _xlsx([["Hon", "612", "JUAN PEREZ", 1000, 160, 106.67, 100, 953.33, "PEXJ800101ABC", "Agosto", 2026]])
    filas = parsear_excel_montos(data)
    assert filas[0].mes == 8


def test_sin_columnas_mes_anio_quedan_none():
    header = HEADER[:8]  # sin RFC/Mes/Año
    data = _xlsx([["Hon", "612", "JUAN PEREZ", 1000, 160, 106.67, 100, 953.33]], header=header)
    filas = parsear_excel_montos(data)
    assert filas[0].mes is None
    assert filas[0].anio is None
    assert filas[0].rfc_emisor is None


def test_nombre_se_normaliza():
    data = _xlsx([["Hon", "612", "  José  Pérez  ", 1000, 160, 106.67, 100, 953.33, "PEXJ800101ABC", 6, 2026]])
    filas = parsear_excel_montos(data)
    assert filas[0].nombre_emisor == "JOSE PEREZ"
