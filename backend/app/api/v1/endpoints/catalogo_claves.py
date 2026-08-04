import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_revisor
from app.models.catalogo_clave import CatalogoClave
from app.models.usuario import Usuario
from app.schemas.catalogo_clave import (
    CatalogoClaveCreate,
    CatalogoClaveLoteCreate,
    CatalogoClaveLoteOut,
    CatalogoClaveOut,
    CatalogoClaveUpdate,
)
from app.services import audit

router = APIRouter()

_TIPOS_VALIDOS = {"servicio", "unidad"}
_CON_PUNTO_DECIMAL_RE = re.compile(r"\d\.\d")


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
    if payload.tipo not in _TIPOS_VALIDOS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="tipo debe ser 'servicio' o 'unidad'")
    if _CON_PUNTO_DECIMAL_RE.search(payload.clave):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                             detail=f"La clave no puede tener punto decimal: {payload.clave}")
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


@router.post("/lote", response_model=CatalogoClaveLoteOut, status_code=status.HTTP_201_CREATED,
             summary="Alta de varias claves SAT en un solo envío, evitando duplicados")
def crear_claves_lote(
    payload: CatalogoClaveLoteCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    existentes = {c.clave for c in db.query(CatalogoClave.clave).all()}
    creadas = 0
    omitidas = 0
    errores: list[str] = []
    vistas_en_lote: set[str] = set()

    for item in payload.items:
        clave = item.clave.strip()
        if not clave:
            continue
        if item.tipo not in _TIPOS_VALIDOS:
            errores.append(f"{clave}: tipo debe ser 'servicio' o 'unidad'")
            continue
        if _CON_PUNTO_DECIMAL_RE.search(clave):
            errores.append(f"{clave}: no puede tener punto decimal (revisa el formato de esa columna/celda)")
            continue
        if clave in existentes or clave in vistas_en_lote:
            omitidas += 1
            continue
        db.add(CatalogoClave(clave=clave, descripcion=item.descripcion, tipo=item.tipo, activo=item.activo))
        vistas_en_lote.add(clave)
        creadas += 1

    if creadas:
        db.flush()
        audit.log(db, username=user.username, rol=user.rol, accion="CREATE",
                  recurso="catalogo_clave", recurso_id="lote",
                  detalle=f"Cargó {creadas} claves SAT en lote ({omitidas} ya existían)")
        db.commit()

    return CatalogoClaveLoteOut(creadas=creadas, existentes=omitidas, errores=errores)


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
