from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.profesor import Profesor
from app.models.usuario import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado o token inválido",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload:
        raise exc
    user = db.query(Usuario).filter(
        Usuario.username == payload["sub"],
        Usuario.activo == True,  # noqa: E712
    ).first()
    if not user:
        raise exc
    return user


def require_superadmin(user: Usuario = Depends(get_current_user)) -> Usuario:
    if user.rol != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol superadmin",
        )
    return user


def require_revisor(user: Usuario = Depends(get_current_user)) -> Usuario:
    """Permite superadmin y revisor."""
    if user.rol not in ("superadmin", "revisor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )
    return user


def require_lectura(user: Usuario = Depends(get_current_user)) -> Usuario:
    """Permite superadmin, revisor y consulta — acceso de solo lectura (GET).
    Los endpoints de escritura de estos mismos routers siguen protegidos
    individualmente con require_revisor/require_superadmin."""
    if user.rol not in ("superadmin", "revisor", "consulta"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado",
        )
    return user


def require_profesor(user: Usuario = Depends(get_current_user)) -> Usuario:
    """Solo el rol 'profesor' — para el portal de consulta."""
    if user.rol != "profesor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol profesor",
        )
    return user


def get_current_profesor(
    user: Usuario = Depends(require_profesor),
    db: Session = Depends(get_db),
) -> Profesor:
    """Resuelve el Profesor ligado al usuario del token (nunca por id del cliente)."""
    if not user.profesor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta no está ligada a un profesor",
        )
    profesor = db.query(Profesor).filter(
        Profesor.id == user.profesor_id,
        Profesor.activo == True,  # noqa: E712
    ).first()
    if not profesor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profesor no encontrado o inactivo",
        )
    return profesor


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
