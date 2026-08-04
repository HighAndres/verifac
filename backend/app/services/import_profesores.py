"""Importación masiva de PROFESORES desde el Excel base (formato "Ejemplo Base BBVA").

Reemplaza la vieja captura de facturas por Excel: este archivo son los datos fijos
del profesor, no facturas. Por cada fila hace upsert del profesor (por RFC), le asigna
su clave de servicio autorizada (creándola en el catálogo si falta) y, al terminar,
re-enlaza los montos mensuales que habían quedado sin profesor.

Parseo por ENCABEZADO (tolerante al orden de columnas).
"""
import io
import re
from dataclasses import dataclass, field
from typing import Optional

import openpyxl
from sqlalchemy.orm import Session

from app.models.catalogo_clave import CatalogoClave
from app.models.monto_mensual import MontoMensual
from app.models.profesor import Profesor
from app.models.profesor_clave import ProfesorClave
from app.services.excel_montos_parser import normalizar_nombre

_RFC_RE = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")
_REGIMENES = {"626", "612", "603"}
_CON_PUNTO_DECIMAL_RE = re.compile(r"\d\.\d")

# Encabezados aceptados por campo (comparados con normalizar_nombre → mayúsculas sin acentos).
_COLS = {
    "nombre": ("NOMBRE EMISOR", "NOMBRE EMISIOR", "NOMBRE"),
    "rfc": ("RFC",),
    "correo": ("CORREO", "EMAIL", "CORREO ELECTRONICO"),
    "regimen": ("CLAVE REGIMEN EMISOR", "REGIMEN EMISOR", "REGIMEN FISCAL", "REGIMEN"),
    "clave_serv": ("CLAVE PROD/SERV", "CLAVE PRODSERV", "CLAVE SERVICIO", "CLAVE DE SERVICIO"),
    "concepto": ("CONCEPTO DE SERVICIO", "CONCEPTO", "DESCRIPCION"),
}


@dataclass
class ResultadoImport:
    total_filas: int = 0
    creados: int = 0
    actualizados: int = 0
    claves_nuevas_catalogo: int = 0
    claves_asignadas: int = 0
    montos_reenlazados: int = 0
    errores: list[dict] = field(default_factory=list)


def _mapear_columnas(encabezado) -> dict[str, int]:
    idx: dict[str, int] = {}
    for i, celda in enumerate(encabezado or []):
        if celda is None:
            continue
        norm = normalizar_nombre(celda)
        for campo, alias in _COLS.items():
            if campo not in idx and norm in alias:
                idx[campo] = i
    return idx


def _val(row, idx: Optional[int]) -> str:
    if idx is None or idx >= len(row) or row[idx] is None:
        return ""
    return str(row[idx]).strip()


def _catalogo_por_clave(db: Session) -> dict[str, CatalogoClave]:
    return {c.clave: c for c in db.query(CatalogoClave).all()}


def importar_profesores(contenido: bytes, db: Session) -> ResultadoImport:
    wb = openpyxl.load_workbook(io.BytesIO(contenido), data_only=True, read_only=True)
    ws = wb.active

    filas = list(ws.iter_rows(values_only=True))
    wb.close()
    if not filas:
        raise ValueError("El archivo está vacío")

    cols = _mapear_columnas(filas[0])
    faltan = [c for c in ("nombre", "rfc", "regimen") if c not in cols]
    if faltan:
        raise ValueError(
            "Faltan columnas obligatorias en el encabezado: "
            + ", ".join({"nombre": "Nombre", "rfc": "RFC", "regimen": "Régimen"}[c] for c in faltan)
        )

    res = ResultadoImport()
    catalogo = _catalogo_por_clave(db)

    for n, row in enumerate(filas[1:], start=2):
        if not any(row):
            continue
        res.total_filas += 1

        nombre = _val(row, cols.get("nombre"))
        rfc = _val(row, cols.get("rfc")).upper()
        regimen = _val(row, cols.get("regimen"))
        correo = _val(row, cols.get("correo"))
        clave_serv = _val(row, cols.get("clave_serv"))
        concepto = _val(row, cols.get("concepto"))

        if not nombre:
            res.errores.append({"fila": n, "motivo": "Falta el nombre"})
            continue
        if not _RFC_RE.match(rfc):
            res.errores.append({"fila": n, "motivo": f"RFC inválido: {rfc or '(vacío)'}"})
            continue
        if regimen not in _REGIMENES:
            res.errores.append({"fila": n, "motivo": f"Régimen inválido: {regimen or '(vacío)'} (debe ser 626/612/603)"})
            continue
        if clave_serv and _CON_PUNTO_DECIMAL_RE.search(clave_serv):
            res.errores.append({
                "fila": n,
                "motivo": f"Clave prod/serv con punto decimal: {clave_serv} (revisa el formato de esa columna en el Excel, "
                          "seguramente quedó como número en vez de texto)",
            })
            continue

        # ── Upsert del profesor por RFC ──────────────────────────────────────
        profesor = db.query(Profesor).filter(Profesor.rfc == rfc).first()
        if profesor:
            profesor.nombre = nombre
            profesor.regimen_fiscal = regimen
            if correo:   # no pisar un correo real con placeholder
                if not db.query(Profesor).filter(Profesor.correo == correo, Profesor.id != profesor.id).first():
                    profesor.correo = correo
            res.actualizados += 1
        else:
            correo_final = correo or f"{rfc.lower()}@pendiente.local"
            if db.query(Profesor).filter(Profesor.correo == correo_final).first():
                res.errores.append({"fila": n, "motivo": f"El correo ya está registrado: {correo_final}"})
                continue
            profesor = Profesor(rfc=rfc, nombre=nombre, correo=correo_final,
                                regimen_fiscal=regimen, activo=True)
            db.add(profesor)
            db.flush()
            res.creados += 1

        # ── Clave de servicio autorizada ─────────────────────────────────────
        if clave_serv:
            cat = catalogo.get(clave_serv)
            if cat is None:
                cat = CatalogoClave(clave=clave_serv,
                                    descripcion=concepto or f"Servicio {clave_serv}",
                                    tipo="servicio", activo=True)
                db.add(cat)
                db.flush()
                catalogo[clave_serv] = cat
                res.claves_nuevas_catalogo += 1
            ya = db.query(ProfesorClave).filter(
                ProfesorClave.profesor_id == profesor.id,
                ProfesorClave.catalogo_clave_id == cat.id,
            ).first()
            if not ya:
                db.add(ProfesorClave(profesor_id=profesor.id, catalogo_clave_id=cat.id))
                res.claves_asignadas += 1

    # ── Re-enlace de montos que quedaron sin profesor ────────────────────────
    res.montos_reenlazados = _reenlazar_montos(db)

    db.commit()
    return res


def _reenlazar_montos(db: Session) -> int:
    """Asigna profesor_id a los MontoMensual sueltos, emparejando por RFC o nombre."""
    sueltos = db.query(MontoMensual).filter(MontoMensual.profesor_id.is_(None)).all()
    if not sueltos:
        return 0
    profesores = db.query(Profesor).all()
    por_rfc = {p.rfc.upper(): p for p in profesores if p.rfc}
    por_nombre = {normalizar_nombre(p.nombre): p for p in profesores}
    n = 0
    for m in sueltos:
        prof = None
        if m.rfc_emisor:
            prof = por_rfc.get(m.rfc_emisor.upper())
        if prof is None and m.nombre_layout:
            prof = por_nombre.get(normalizar_nombre(m.nombre_layout))
        if prof:
            m.profesor_id = prof.id
            n += 1
    return n
