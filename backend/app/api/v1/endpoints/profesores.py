from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db, require_revisor
from app.models.profesor import Profesor
from app.models.usuario import Usuario
from app.schemas.profesor import ProfesorCreate, ProfesorListOut, ProfesorOut, ProfesorUpdate
from app.services import audit
from app.services.import_profesores import importar_profesores

router = APIRouter()


@router.post("/importar", summary="Alta/actualización masiva de profesores desde Excel base (.xlsx)")
def importar(
    file: UploadFile,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="El archivo debe ser .xlsx")

    from app.core.config import settings
    contenido = file.file.read()
    if len(contenido) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=422, detail=f"El archivo supera el límite de {settings.MAX_UPLOAD_MB} MB")

    try:
        res = importar_profesores(contenido, db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    audit.log(db, username=user.username, rol=user.rol, accion="IMPORT",
              recurso="profesores", recurso_id=file.filename,
              detalle=f"creados={res.creados} actualizados={res.actualizados} "
                      f"claves_nuevas={res.claves_nuevas_catalogo} errores={len(res.errores)}",
              ip=get_client_ip(request))

    return {
        "total_filas": res.total_filas,
        "creados": res.creados,
        "actualizados": res.actualizados,
        "claves_nuevas_catalogo": res.claves_nuevas_catalogo,
        "claves_asignadas": res.claves_asignadas,
        "montos_reenlazados": res.montos_reenlazados,
        "errores": res.errores,
    }


def _get_or_404(db: Session, profesor_id: UUID) -> Profesor:
    p = db.query(Profesor).filter(Profesor.id == profesor_id).first()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profesor no encontrado")
    return p


@router.get("", response_model=ProfesorListOut)
def listar_profesores(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    activo: Optional[bool] = Query(None),
    q: Optional[str] = Query(None, description="Buscar por nombre o RFC"),
    db: Session = Depends(get_db),
):
    query = db.query(Profesor)
    if activo is not None:
        query = query.filter(Profesor.activo == activo)
    if q:
        like = f"%{q.upper()}%"
        query = query.filter(
            Profesor.rfc.ilike(like) | Profesor.nombre.ilike(f"%{q}%")
        )
    total = query.count()
    items = query.order_by(Profesor.nombre).offset(skip).limit(limit).all()

    cuentas = {}
    if items:
        cuentas = {
            u.profesor_id: u.username
            for u in db.query(Usuario.profesor_id, Usuario.username)
            .filter(Usuario.profesor_id.in_([p.id for p in items]))
            .all()
        }
    items_out = [
        {
            **ProfesorOut.model_validate(p).model_dump(),
            "tiene_cuenta": p.id in cuentas,
            "cuenta_username": cuentas.get(p.id),
        }
        for p in items
    ]
    return {"total": total, "items": items_out}


@router.post("", response_model=ProfesorOut, status_code=status.HTTP_201_CREATED)
def crear_profesor(
    payload: ProfesorCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    if db.query(Profesor).filter(Profesor.rfc == payload.rfc).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="RFC ya registrado")
    if db.query(Profesor).filter(Profesor.correo == payload.correo).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Correo ya registrado")

    profesor = Profesor(**payload.model_dump())
    db.add(profesor)
    db.flush()
    audit.log(db, username=user.username, rol=user.rol, accion="CREATE",
              recurso="profesor", recurso_id=str(profesor.id),
              detalle=f"Creó profesor RFC={payload.rfc} nombre={payload.nombre}",
              ip=get_client_ip(request))
    db.commit()
    db.refresh(profesor)
    return profesor


@router.get("/{profesor_id}", response_model=ProfesorOut)
def obtener_profesor(profesor_id: UUID, db: Session = Depends(get_db)):
    profesor = _get_or_404(db, profesor_id)
    cuenta = db.query(Usuario.username).filter(Usuario.profesor_id == profesor_id).first()
    return {
        **ProfesorOut.model_validate(profesor).model_dump(),
        "tiene_cuenta": cuenta is not None,
        "cuenta_username": cuenta[0] if cuenta else None,
    }


@router.patch("/{profesor_id}", response_model=ProfesorOut)
def actualizar_profesor(
    profesor_id: UUID,
    payload: ProfesorUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    profesor = _get_or_404(db, profesor_id)
    cambios = payload.model_dump(exclude_unset=True)

    if "correo" in cambios:
        dup = db.query(Profesor).filter(
            Profesor.correo == cambios["correo"], Profesor.id != profesor_id
        ).first()
        if dup:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Correo ya registrado")

    for campo, valor in cambios.items():
        setattr(profesor, campo, valor)

    audit.log(db, username=user.username, rol=user.rol, accion="UPDATE",
              recurso="profesor", recurso_id=str(profesor_id),
              detalle=f"Editó {list(cambios.keys())} de RFC={profesor.rfc}",
              ip=get_client_ip(request))
    db.commit()
    db.refresh(profesor)
    return profesor


@router.delete("/{profesor_id}", status_code=status.HTTP_204_NO_CONTENT)
def desactivar_profesor(
    profesor_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    profesor = _get_or_404(db, profesor_id)
    profesor.activo = False
    audit.log(db, username=user.username, rol=user.rol, accion="DELETE",
              recurso="profesor", recurso_id=str(profesor_id),
              detalle=f"Desactivó profesor RFC={profesor.rfc}",
              ip=get_client_ip(request))
    db.commit()
