from typing import Optional
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


def log(
    db: Session,
    username: str,
    accion: str,
    rol: Optional[str] = None,
    recurso: Optional[str] = None,
    recurso_id: Optional[str] = None,
    detalle: Optional[str] = None,
    ip: Optional[str] = None,
) -> None:
    db.add(AuditLog(
        username=username,
        rol=rol,
        accion=accion,
        recurso=recurso,
        recurso_id=str(recurso_id) if recurso_id else None,
        detalle=detalle,
        ip=ip,
    ))
    db.commit()
