from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sqlalchemy import func

from app.api.deps import get_client_ip, get_current_user
from app.core.emails import es_placeholder, normalizar_correo
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
    correo = normalizar_correo(form.username)

    try:
        rl_check(ip)   # máximo 10 intentos por IP en 15 min
    except HTTPException:
        audit.log(db, username=correo or form.username, accion="LOGIN_BLOCKED",
                  detalle="IP bloqueada temporalmente por demasiados intentos fallidos", ip=ip)
        raise

    # El acceso es por CORREO (el campo del formulario OAuth2 se llama "username"
    # por el estándar, pero contiene el correo). Se compara normalizado y sin
    # distinguir mayúsculas; los correos placeholder no son credencial válida.
    user = None
    if correo and not es_placeholder(correo):
        user = db.query(Usuario).filter(
            func.lower(Usuario.correo) == correo,
            Usuario.activo == True,  # noqa: E712
        ).first()

    if not user or not verify_password(form.password, user.password_hash):
        audit.log(db, username=correo or form.username, accion="LOGIN_FAILED",
                  detalle="Correo no encontrado o inactivo" if not user else "Contraseña incorrecta",
                  ip=ip)
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
