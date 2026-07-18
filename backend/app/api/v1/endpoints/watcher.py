from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db, SessionLocal
from app.services.imap_watcher import revisar_correo

router = APIRouter()


def _imap_config_ok() -> bool:
    return bool(
        settings.IMAP_PASSWORD
        and settings.IMAP_PASSWORD != "pon-aqui-tu-app-password"
    )


@router.get("/status")
def estado_watcher(_: str = Depends(get_current_user)):
    return {
        "configurado": _imap_config_ok(),
        "cuenta": settings.IMAP_USER,
        "host": settings.IMAP_HOST,
        "poll_minutos": settings.IMAP_POLL_MINUTES,
        "instrucciones": (
            None if _imap_config_ok()
            else "Genera un App Password en myaccount.google.com → Seguridad → "
                 "Verificación en dos pasos → Contraseñas de aplicaciones, "
                 "y ponlo en IMAP_PASSWORD del .env"
        ),
    }


@router.post("/run")
def ejecutar_watcher(_: str = Depends(get_current_user)):
    if not _imap_config_ok():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IMAP no configurado. Agrega IMAP_PASSWORD en el .env.",
        )
    db = SessionLocal()
    try:
        resultado = revisar_correo(
            db=db,
            imap_host=settings.IMAP_HOST,
            imap_port=settings.IMAP_PORT,
            imap_user=settings.IMAP_USER,
            imap_password=settings.IMAP_PASSWORD,
            imap_folder=settings.IMAP_FOLDER,
        )
    finally:
        db.close()

    return resultado
