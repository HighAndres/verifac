from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_user
from app.core.security import create_access_token, verify_password
from app.core.rate_limit import check as rl_check, reset as rl_reset
from app.db.session import get_db
from app.models.usuario import Usuario
from app.services import audit

router = APIRouter()


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: str
    nombre: str


@router.post("/login", response_model=Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    request: Request = None,
):
    ip = get_client_ip(request) if request else "unknown"
    rl_check(ip)   # máximo 10 intentos por IP en 15 min

    user = db.query(Usuario).filter(
        Usuario.username == form.username,
        Usuario.activo == True,  # noqa: E712
    ).first()

    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    rl_reset(ip)   # login exitoso — resetea contador
    # Actualizar último acceso
    user.ultimo_acceso = datetime.now(timezone.utc)
    db.commit()

    # Auditoría
    audit.log(db, username=user.username, rol=user.rol, accion="LOGIN",
              ip=get_client_ip(request) if request else None)

    return Token(
        access_token=create_access_token(user.username, user.rol),
        rol=user.rol,
        nombre=user.nombre,
    )


@router.get("/me")
def me(user: Usuario = Depends(get_current_user)):
    return {"username": user.username, "nombre": user.nombre, "rol": user.rol}
