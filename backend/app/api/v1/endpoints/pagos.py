"""Pantalla de Pagos (revisor + superadmin): marca de pago por profesor y mes."""
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_revisor
from app.db.session import get_db
from app.models.pago import Pago
from app.models.profesor import Profesor
from app.models.usuario import Usuario
from app.services import audit
from app.services.pagos import lista_mensual

router = APIRouter()

_METODOS = {"Transferencia", "Cheque", "Efectivo", "Otro"}
_INCIDENCIAS = {"Error en factura", "Trámite en SAT", "Error en cuenta bancaria"}


class PagoUpsert(BaseModel):
    profesor_id: UUID
    mes: int
    anio: int
    pagada: bool = False
    fecha_pago: Optional[date] = None
    metodo_pago: Optional[str] = None
    incidencia: Optional[str] = None


@router.get("")
def listar_pagos(
    mes: int = Query(..., ge=1, le=12),
    anio: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
):
    return {"mes": mes, "anio": anio, "items": lista_mensual(db, mes, anio)}


@router.put("")
def guardar_pago(
    payload: PagoUpsert,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    if not (1 <= payload.mes <= 12):
        raise HTTPException(status_code=422, detail="mes fuera de rango")
    if payload.metodo_pago and payload.metodo_pago not in _METODOS:
        raise HTTPException(status_code=422, detail=f"metodo_pago debe ser uno de: {sorted(_METODOS)}")
    if payload.incidencia and payload.incidencia not in _INCIDENCIAS:
        raise HTTPException(status_code=422, detail=f"incidencia debe ser una de: {sorted(_INCIDENCIAS)}")
    if not db.query(Profesor).filter(Profesor.id == payload.profesor_id).first():
        raise HTTPException(status_code=404, detail="Profesor no encontrado")

    pago = (
        db.query(Pago)
        .filter(Pago.profesor_id == payload.profesor_id, Pago.mes == payload.mes, Pago.anio == payload.anio)
        .first()
    )
    if pago is None:
        pago = Pago(profesor_id=payload.profesor_id, mes=payload.mes, anio=payload.anio)
        db.add(pago)

    pago.pagada = payload.pagada
    # Si se desmarca como pagada, se limpian fecha/método para no dejar datos huérfanos.
    # La incidencia es independiente de "pagada" (puede registrarse en cualquier momento).
    if payload.pagada:
        pago.fecha_pago = payload.fecha_pago
        pago.metodo_pago = payload.metodo_pago
    else:
        pago.fecha_pago = None
        pago.metodo_pago = None
    pago.incidencia = payload.incidencia
    pago.registrado_por = user.username

    audit.log(db, username=user.username, rol=user.rol, accion="UPDATE",
              recurso="pago", recurso_id=f"{payload.profesor_id}:{payload.mes:02d}/{payload.anio}",
              detalle=f"pagada={payload.pagada}")
    db.commit()
    db.refresh(pago)

    return {
        "profesor_id": str(pago.profesor_id),
        "mes": pago.mes,
        "anio": pago.anio,
        "pagada": pago.pagada,
        "fecha_pago": pago.fecha_pago.isoformat() if pago.fecha_pago else None,
        "metodo_pago": pago.metodo_pago,
        "incidencia": pago.incidencia,
        "registrado_por": pago.registrado_por,
    }
