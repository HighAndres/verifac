from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_revisor
from app.models.catalogo_clave import CatalogoClave
from app.models.usuario import Usuario
from app.schemas.catalogo_clave import CatalogoClaveCreate, CatalogoClaveOut, CatalogoClaveUpdate
from app.services import audit

router = APIRouter()


def _get_or_404(db: Session, clave_id: UUID) -> CatalogoClave:
    obj = db.query(CatalogoClave).filter(CatalogoClave.id == clave_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clave no encontrada")
    return obj


@router.get("", response_model=list[CatalogoClaveOut])
def listar_claves(
    tipo: str | None = Query(None, pattern="^(servicio|unidad)$"),
    activo: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(CatalogoClave)
    if tipo is not None:
        q = q.filter(CatalogoClave.tipo == tipo)
    if activo is not None:
        q = q.filter(CatalogoClave.activo == activo)
    return q.order_by(CatalogoClave.clave).all()


@router.post("", response_model=CatalogoClaveOut, status_code=status.HTTP_201_CREATED)
def crear_clave(
    payload: CatalogoClaveCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    if db.query(CatalogoClave).filter(CatalogoClave.clave == payload.clave).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Clave ya existe en catálogo")
    obj = CatalogoClave(**payload.model_dump())
    db.add(obj)
    db.flush()
    audit.log(db, username=user.username, rol=user.rol, accion="CREATE",
              recurso="catalogo_clave", recurso_id=str(obj.id),
              detalle=f"Agregó clave SAT {payload.clave} ({payload.tipo})")
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{clave_id}", response_model=CatalogoClaveOut)
def actualizar_clave(
    clave_id: UUID,
    payload: CatalogoClaveUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    obj = _get_or_404(db, clave_id)
    cambios = payload.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(obj, campo, valor)
    audit.log(db, username=user.username, rol=user.rol, accion="UPDATE",
              recurso="catalogo_clave", recurso_id=str(clave_id),
              detalle=f"Editó clave {obj.clave}: {list(cambios.keys())}")
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{clave_id}", status_code=status.HTTP_204_NO_CONTENT)
def desactivar_clave(
    clave_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    obj = _get_or_404(db, clave_id)
    obj.activo = False
    audit.log(db, username=user.username, rol=user.rol, accion="DELETE",
              recurso="catalogo_clave", recurso_id=str(clave_id),
              detalle=f"Desactivó clave {obj.clave}")
    db.commit()
