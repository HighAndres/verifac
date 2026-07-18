"""
Parser del archivo "Ejemplo Base BBVA.xlsx".
Lee cada fila de datos y la convierte en un dict normalizado listo para validar.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

import openpyxl

# Índices de columna (0-based) según el encabezado del archivo
COL = {
    "categoria":        0,
    "fecha_emision":    1,
    "uso_cfdi":         2,
    "clave_servicio":   3,
    "descripcion":      4,
    "regimen_emisor":   5,
    "regimen_nombre":   6,
    "nombre_emisor":    7,
    "nombre_receptor":  10,
    "unidad":           11,
    "subtotal":         14,
    "iva_trasladado":   15,
    "iva_retenido":     16,
    "isr_retenido":     17,
    "total":            18,
    "moneda":           19,
    "forma_pago":       20,
    "metodo_pago":      21,
}


@dataclass
class FilaExcel:
    fila: int
    categoria: str
    fecha_texto: str
    uso_cfdi: str
    clave_servicio: str
    descripcion: str
    regimen_emisor: str
    nombre_emisor: str
    nombre_receptor: str
    unidad: str
    subtotal: Decimal
    iva_trasladado: Decimal
    iva_retenido: Decimal
    isr_retenido: Decimal
    total: Decimal
    moneda: str
    forma_pago: str
    metodo_pago: str


def _str(val) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _dec(val) -> Decimal:
    if val is None:
        return Decimal("0")
    try:
        return Decimal(str(val)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0")


def parsear_excel(xlsx_bytes: bytes) -> list[FilaExcel]:
    """
    Lee el archivo XLSX y retorna una lista de FilaExcel por cada fila con datos.
    Ignora la fila de encabezado y las filas vacías.
    """
    from io import BytesIO
    wb = openpyxl.load_workbook(BytesIO(xlsx_bytes), data_only=True, read_only=True)
    ws = wb.active

    filas: list[FilaExcel] = []

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:          # encabezado
            continue
        if all(c is None for c in row):
            continue        # fila vacía

        subtotal = _dec(row[COL["subtotal"]])
        if subtotal == 0:
            continue        # fila sin datos reales

        filas.append(FilaExcel(
            fila=i + 1,
            categoria=_str(row[COL["categoria"]]),
            fecha_texto=_str(row[COL["fecha_emision"]]),
            uso_cfdi=_str(row[COL["uso_cfdi"]]),
            clave_servicio=_str(row[COL["clave_servicio"]]),
            descripcion=_str(row[COL["descripcion"]]),
            regimen_emisor=_str(row[COL["regimen_emisor"]]),
            nombre_emisor=_str(row[COL["nombre_emisor"]]),
            nombre_receptor=_str(row[COL["nombre_receptor"]]),
            unidad=_str(row[COL["unidad"]]),
            subtotal=subtotal,
            iva_trasladado=_dec(row[COL["iva_trasladado"]]),
            iva_retenido=_dec(row[COL["iva_retenido"]]),
            isr_retenido=_dec(row[COL["isr_retenido"]]),
            total=_dec(row[COL["total"]]),
            moneda=_str(row[COL["moneda"]]),
            forma_pago=_str(row[COL["forma_pago"]]),
            metodo_pago=_str(row[COL["metodo_pago"]]),
        ))

    wb.close()
    return filas
