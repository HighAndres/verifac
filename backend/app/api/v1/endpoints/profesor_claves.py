from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_revisor
from app.db.session import get_db
from app.models.catalogo_clave import CatalogoClave
from app.models.profesor import Profesor
from app.models.profesor_clave import ProfesorClave
from app.models.usuario import Usuario
from app.services import audit

router = APIRouter()


class ClaveAsignadaOut(BaseModel):
    id: UUID
    catalogo_clave_id: UUID
    clave: str
    descripcion: str
    tipo: str

    model_config = {"from_attributes": False}


def _profesor_or_404(db: Session, profesor_id: UUID) -> Profesor:
    p = db.query(Profesor).filter(Profesor.id == profesor_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Profesor no encontrado")
    return p


@router.get("/{profesor_id}/claves", response_model=list[ClaveAsignadaOut])
def listar_claves_profesor(
    profesor_id: UUID,
    db: Session = Depends(get_db),
):
    _profesor_or_404(db, profesor_id)
    rows = (
        db.query(ProfesorClave, CatalogoClave)
        .join(CatalogoClave, ProfesorClave.catalogo_clave_id == CatalogoClave.id)
        .filter(ProfesorClave.profesor_id == profesor_id)
        .all()
    )
    return [
        ClaveAsignadaOut(
            id=pc.id,
            catalogo_clave_id=cat.id,
            clave=cat.clave,
            descripcion=cat.descripcion,
            tipo=cat.tipo,
        )
        for pc, cat in rows
    ]


@router.post(
    "/{profesor_id}/claves/{clave_id}",
    response_model=ClaveAsignadaOut,
    status_code=status.HTTP_201_CREATED,
)
def asignar_clave(
    profesor_id: UUID,
    clave_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    profesor = _profesor_or_404(db, profesor_id)
    cat = db.query(CatalogoClave).filter(CatalogoClave.id == clave_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Clave de catálogo no encontrada")
    if cat.tipo != "servicio":
        raise HTTPException(
            status_code=422,
            detail="Solo se pueden asignar claves de tipo 'servicio' — las de unidad son globales",
        )

    existe = (
        db.query(ProfesorClave)
        .filter(ProfesorClave.profesor_id == profesor_id, ProfesorClave.catalogo_clave_id == clave_id)
        .first()
    )
    if existe:
        raise HTTPException(status_code=409, detail="La clave ya está asignada a este profesor")

    pc = ProfesorClave(profesor_id=profesor_id, catalogo_clave_id=clave_id)
    db.add(pc)
    db.flush()
    audit.log(db, username=user.username, rol=user.rol, accion="CREATE",
              recurso="profesor_clave", recurso_id=str(pc.id),
              detalle=f"Asignó clave {cat.clave} a profesor RFC={profesor.rfc}",
              ip=get_client_ip(request))
    db.commit()
    db.refresh(pc)
    return ClaveAsignadaOut(id=pc.id, catalogo_clave_id=cat.id, clave=cat.clave, descripcion=cat.descripcion, tipo=cat.tipo)


@router.delete("/{profesor_id}/claves/{clave_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_clave(
    profesor_id: UUID,
    clave_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_revisor),
):
    profesor = _profesor_or_404(db, profesor_id)
    pc = (
        db.query(ProfesorClave)
        .filter(ProfesorClave.profesor_id == profesor_id, ProfesorClave.catalogo_clave_id == clave_id)
        .first()
    )
    if not pc:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    cat = db.query(CatalogoClave).filter(CatalogoClave.id == clave_id).first()
    db.delete(pc)
    audit.log(db, username=user.username, rol=user.rol, accion="DELETE",
              recurso="profesor_clave", recurso_id=str(pc.id),
              detalle=f"Removió clave {cat.clave if cat else clave_id} de profesor RFC={profesor.rfc}",
              ip=get_client_ip(request))
    db.commit()
