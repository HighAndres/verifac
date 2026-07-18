from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_revisor
from app.db.session import get_db
from app.models.catalogo_clave import CatalogoClave
from app.models.profesor import Profesor
from app.models.profesor_clave import ProfesorClave

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
    _: object = Depends(require_revisor),
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
    db: Session = Depends(get_db),
    _: object = Depends(require_revisor),
):
    _profesor_or_404(db, profesor_id)
    cat = db.query(CatalogoClave).filter(CatalogoClave.id == clave_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Clave de catálogo no encontrada")

    existe = (
        db.query(ProfesorClave)
        .filter(ProfesorClave.profesor_id == profesor_id, ProfesorClave.catalogo_clave_id == clave_id)
        .first()
    )
    if existe:
        raise HTTPException(status_code=409, detail="La clave ya está asignada a este profesor")

    pc = ProfesorClave(profesor_id=profesor_id, catalogo_clave_id=clave_id)
    db.add(pc)
    db.commit()
    db.refresh(pc)
    return ClaveAsignadaOut(id=pc.id, catalogo_clave_id=cat.id, clave=cat.clave, descripcion=cat.descripcion, tipo=cat.tipo)


@router.delete("/{profesor_id}/claves/{clave_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_clave(
    profesor_id: UUID,
    clave_id: UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_revisor),
):
    pc = (
        db.query(ProfesorClave)
        .filter(ProfesorClave.profesor_id == profesor_id, ProfesorClave.catalogo_clave_id == clave_id)
        .first()
    )
    if not pc:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    db.delete(pc)
    db.commit()
