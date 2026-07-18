from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_superadmin
from app.models.audit_log import AuditLog
from app.models.usuario import Usuario

router = APIRouter()


class AuditLogOut(BaseModel):
    id: UUID
    username: str
    rol: Optional[str]
    accion: str
    recurso: Optional[str]
    recurso_id: Optional[str]
    detalle: Optional[str]
    ip: Optional[str]
    timestamp: datetime

    model_config = {"from_attributes": True}


class AuditListOut(BaseModel):
    total: int
    items: list[AuditLogOut]


@router.get("", response_model=AuditListOut)
def listar_auditoria(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    username: Optional[str] = Query(None),
    accion: Optional[str] = Query(None),
    recurso: Optional[str] = Query(None),
    desde: Optional[datetime] = Query(None),
    hasta: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_superadmin),
):
    q = db.query(AuditLog)

    if username:
        q = q.filter(AuditLog.username.ilike(f"%{username}%"))
    if accion:
        q = q.filter(AuditLog.accion == accion.upper())
    if recurso:
        q = q.filter(AuditLog.recurso == recurso.lower())
    if desde:
        q = q.filter(AuditLog.timestamp >= desde)
    if hasta:
        q = q.filter(AuditLog.timestamp <= hasta)

    total = q.count()
    items = q.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": items}
