from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db, require_superadmin
from app.core.security import hash_password
from app.models.profesor import Profesor
from app.models.usuario import Usuario
from app.services import audit
from fastapi import Request

router = APIRouter()

_ROLES = ("superadmin", "revisor", "profesor")


class UsuarioCreate(BaseModel):
    username: str
    nombre: str
    password: str
    rol: str = "revisor"
    profesor_id: Optional[UUID] = None


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[str] = None
    activo: Optional[bool] = None
    profesor_id: Optional[UUID] = None


class UsuarioOut(BaseModel):
    id: UUID
    username: str
    nombre: str
    rol: str
    profesor_id: Optional[UUID] = None
    activo: bool
    ultimo_acceso: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_custom(cls, u: Usuario):
        return cls(
            id=u.id,
            username=u.username,
            nombre=u.nombre,
            rol=u.rol,
            profesor_id=u.profesor_id,
            activo=u.activo,
            ultimo_acceso=u.ultimo_acceso.isoformat() if u.ultimo_acceso else None,
            created_at=u.created_at.isoformat(),
        )


def _validar_profesor_ligado(db: Session, rol: str, profesor_id: Optional[UUID], excluir_usuario: Optional[UUID] = None) -> Optional[UUID]:
    """Reglas de coherencia entre rol y profesor_id.

    - rol 'profesor'  → profesor_id obligatorio, el profesor debe existir y no puede
      estar ya ligado a otra cuenta.
    - otros roles      → profesor_id se fuerza a None.
    Devuelve el profesor_id normalizado.
    """
    if rol != "profesor":
        return None
    if profesor_id is None:
        raise HTTPException(status_code=422, detail="El rol 'profesor' requiere profesor_id")
    if not db.query(Profesor).filter(Profesor.id == profesor_id).first():
        raise HTTPException(status_code=404, detail="Profesor no encontrado")
    dup_q = db.query(Usuario).filter(Usuario.profesor_id == profesor_id)
    if excluir_usuario:
        dup_q = dup_q.filter(Usuario.id != excluir_usuario)
    if dup_q.first():
        raise HTTPException(status_code=409, detail="Ese profesor ya tiene una cuenta de acceso")
    return profesor_id


@router.get("", response_model=list[UsuarioOut])
def listar_usuarios(
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_superadmin),
):
    return [UsuarioOut.from_orm_custom(u) for u in db.query(Usuario).order_by(Usuario.created_at).all()]


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    payload: UsuarioCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_superadmin),
):
    if payload.rol not in _ROLES:
        raise HTTPException(status_code=422, detail=f"rol debe ser uno de: {list(_ROLES)}")
    if db.query(Usuario).filter(Usuario.username == payload.username).first():
        raise HTTPException(status_code=409, detail="Username ya existe")

    profesor_id = _validar_profesor_ligado(db, payload.rol, payload.profesor_id)

    user = Usuario(
        username=payload.username,
        nombre=payload.nombre,
        password_hash=hash_password(payload.password),
        rol=payload.rol,
        profesor_id=profesor_id,
    )
    db.add(user)
    db.flush()
    audit.log(db, username=admin.username, rol=admin.rol, accion="CREATE",
              recurso="usuario", recurso_id=str(user.id),
              detalle=f"Creó usuario {payload.username} con rol {payload.rol}",
              ip=get_client_ip(request))
    db.commit()
    db.refresh(user)
    return UsuarioOut.from_orm_custom(user)


@router.patch("/{user_id}", response_model=UsuarioOut)
def actualizar_usuario(
    user_id: UUID,
    payload: UsuarioUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_superadmin),
):
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    cambios = payload.model_dump(exclude_unset=True)
    if "password" in cambios:
        user.password_hash = hash_password(cambios.pop("password"))
    if "rol" in cambios and cambios["rol"] not in _ROLES:
        raise HTTPException(status_code=422, detail=f"rol debe ser uno de: {list(_ROLES)}")

    # Coherencia rol ↔ profesor_id sobre el estado resultante (mezcla lo que cambia
    # con lo que ya tenía el usuario). Normaliza profesor_id a None si el rol no es profesor.
    if "rol" in cambios or "profesor_id" in cambios:
        rol_final = cambios.get("rol", user.rol)
        prof_final = cambios.get("profesor_id", user.profesor_id)
        cambios["profesor_id"] = _validar_profesor_ligado(db, rol_final, prof_final, excluir_usuario=user.id)

    for k, v in cambios.items():
        setattr(user, k, v)

    audit.log(db, username=admin.username, rol=admin.rol, accion="UPDATE",
              recurso="usuario", recurso_id=str(user_id),
              detalle=f"Editó usuario {user.username}: {list(cambios.keys())}",
              ip=get_client_ip(request))
    db.commit()
    db.refresh(user)
    return UsuarioOut.from_orm_custom(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_superadmin),
):
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if str(user.id) == str(admin.id):
        raise HTTPException(status_code=400, detail="No puedes eliminarte a ti mismo")

    audit.log(db, username=admin.username, rol=admin.rol, accion="DELETE",
              recurso="usuario", recurso_id=str(user_id),
              detalle=f"Eliminó usuario {user.username}",
              ip=get_client_ip(request))
    db.delete(user)
    db.commit()
