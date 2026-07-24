"""Portal del profesor — consulta de solo lectura.

El profesor inicia sesión con una cuenta de rol 'profesor' ligada a un registro
de `profesores`. Aquí solo puede ver SUS facturas (emparejadas por RFC) y el link
a su carpeta de documentos en Google Drive. El profesor se resuelve siempre desde
el token (get_current_profesor), nunca por un id que mande el cliente.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.api.deps import get_current_profesor, get_db
from app.models.factura import Factura
from app.models.pago import Pago
from app.models.profesor import Profesor
from app.models.validacion_detalle import ValidacionDetalle
from app.schemas.factura import FacturaDetalleOut, FacturaListOut, FacturaOut

router = APIRouter()

_ESTADOS = {"pendiente", "aprobada", "rechazada"}


class MiPerfilOut(BaseModel):
    id: UUID
    rfc: str
    nombre: str
    correo: str
    regimen_fiscal: str
    drive_url: Optional[str] = None

    model_config = {"from_attributes": True}


@router.get("/mi-perfil", response_model=MiPerfilOut)
def mi_perfil(profesor: Profesor = Depends(get_current_profesor)):
    return profesor


@router.get("/mis-facturas", response_model=FacturaListOut)
def mis_facturas(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    estado: Optional[str] = Query(None),
    mes: Optional[int] = Query(None, ge=1, le=12),
    anio: Optional[int] = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    profesor: Profesor = Depends(get_current_profesor),
):
    if estado and estado not in _ESTADOS:
        raise HTTPException(status_code=422, detail=f"estado debe ser uno de: {sorted(_ESTADOS)}")

    q = db.query(Factura).filter(Factura.rfc_emisor == profesor.rfc)
    if estado:
        q = q.filter(Factura.estado == estado)
    if mes:
        q = q.filter(extract("month", Factura.fecha_emision) == mes)
    if anio:
        q = q.filter(extract("year", Factura.fecha_emision) == anio)

    total = q.count()
    items = q.order_by(Factura.fecha_emision.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": items}


@router.get("/mis-pagos")
def mis_pagos(
    db: Session = Depends(get_db),
    profesor: Profesor = Depends(get_current_profesor),
):
    pagos = (
        db.query(Pago)
        .filter(Pago.profesor_id == profesor.id, Pago.pagada == True)  # noqa: E712
        .order_by(Pago.anio.desc(), Pago.mes.desc())
        .all()
    )
    return {
        "items": [
            {
                "mes": p.mes,
                "anio": p.anio,
                "fecha_pago": p.fecha_pago.isoformat() if p.fecha_pago else None,
                "metodo_pago": p.metodo_pago,
                "monto_pagado": float(p.monto_pagado) if p.monto_pagado is not None else None,
            }
            for p in pagos
        ]
    }


@router.get("/mis-facturas/{factura_id}", response_model=FacturaDetalleOut)
def mi_factura(
    factura_id: UUID,
    db: Session = Depends(get_db),
    profesor: Profesor = Depends(get_current_profesor),
):
    factura = (
        db.query(Factura)
        .filter(Factura.id == factura_id, Factura.rfc_emisor == profesor.rfc)
        .first()
    )
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada")

    detalles = db.query(ValidacionDetalle).filter(ValidacionDetalle.factura_id == factura_id).all()
    return {**FacturaOut.model_validate(factura).model_dump(), "detalles": detalles}
