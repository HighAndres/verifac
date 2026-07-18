from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_superadmin
from app.core.config import settings
from app.db.session import get_db, SessionLocal
from app.models.usuario import Usuario
from app.services import audit
from app.services.config_correo import obtener_config, remitentes_lista, password_configurado
from app.services.email_confirmacion import contar_pendientes, procesar_confirmaciones
from app.services.imap_watcher import revisar_correo

router = APIRouter()


class ConfigCorreoOut(BaseModel):
    imap_host: str
    imap_port: int
    imap_user: str
    imap_folder: str
    poll_minutos: int
    remitentes_permitidos: Optional[str] = None
    auto_activo: bool
    confirmaciones_activas: bool
    password_configurado: bool

    model_config = {"from_attributes": True}


class ConfigCorreoIn(BaseModel):
    imap_host: str = Field(..., min_length=1)
    imap_port: int = Field(..., ge=1, le=65535)
    imap_user: str = Field(..., min_length=1)
    imap_folder: str = Field("INBOX", min_length=1)
    poll_minutos: int = Field(..., ge=1, le=1440)
    remitentes_permitidos: Optional[str] = None
    auto_activo: bool = True
    confirmaciones_activas: bool = False


def _status_payload(db: Session) -> dict:
    cfg = obtener_config(db)
    ok = password_configurado()
    return {
        "configurado": ok,
        "cuenta": cfg.imap_user,
        "host": cfg.imap_host,
        "carpeta": cfg.imap_folder,
        "poll_minutos": cfg.poll_minutos,
        "auto_activo": cfg.auto_activo,
        "confirmaciones_activas": cfg.confirmaciones_activas,
        "confirmaciones_pendientes": contar_pendientes(db),
        "remitentes_permitidos": remitentes_lista(cfg),
        "instrucciones": (
            None if ok
            else "Genera un App Password en myaccount.google.com → Seguridad → "
                 "Verificación en dos pasos → Contraseñas de aplicaciones, "
                 "y ponlo en IMAP_PASSWORD del .env"
        ),
    }


@router.get("/status")
def estado_watcher(_: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    return _status_payload(db)


@router.post("/run")
def ejecutar_watcher(user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    if not password_configurado():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Correo no configurado. Falta la contraseña (IMAP_PASSWORD) en el .env.",
        )
    cfg = obtener_config(db)
    conn = SessionLocal()
    try:
        resultado = revisar_correo(
            db=conn,
            imap_host=cfg.imap_host,
            imap_port=cfg.imap_port,
            imap_user=cfg.imap_user,
            imap_password=settings.IMAP_PASSWORD,
            imap_folder=cfg.imap_folder,
            remitentes_permitidos=remitentes_lista(cfg),
        )
    finally:
        conn.close()

    audit.log(db, username=user.username, rol=user.rol, accion="WATCHER_RUN",
              recurso="correo", detalle=f"procesadas={resultado.get('total_procesadas')} "
                                       f"errores={resultado.get('total_errores')}")
    return resultado


@router.post("/enviar-confirmaciones")
def enviar_confirmaciones(user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """Envío manual: manda las confirmaciones pendientes aunque el modo
    automático esté apagado (la contraseña del buzón sigue siendo requisito)."""
    if not password_configurado():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Correo no configurado. Falta la contraseña (IMAP_PASSWORD) en el .env.",
        )
    resultado = procesar_confirmaciones(db, forzar=True)
    audit.log(db, username=user.username, rol=user.rol, accion="CONFIRMACIONES",
              recurso="correo", detalle=f"enviadas={resultado.get('enviadas')} "
                                        f"errores={resultado.get('errores')}")
    return resultado


@router.get("/config", response_model=ConfigCorreoOut)
def obtener_config_correo(_: Usuario = Depends(require_superadmin), db: Session = Depends(get_db)):
    cfg = obtener_config(db)
    return ConfigCorreoOut(
        imap_host=cfg.imap_host, imap_port=cfg.imap_port, imap_user=cfg.imap_user,
        imap_folder=cfg.imap_folder, poll_minutos=cfg.poll_minutos,
        remitentes_permitidos=cfg.remitentes_permitidos, auto_activo=cfg.auto_activo,
        confirmaciones_activas=cfg.confirmaciones_activas,
        password_configurado=password_configurado(),
    )


@router.put("/config", response_model=ConfigCorreoOut)
def actualizar_config_correo(
    datos: ConfigCorreoIn,
    user: Usuario = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    cfg = obtener_config(db)
    cfg.imap_host = datos.imap_host
    cfg.imap_port = datos.imap_port
    cfg.imap_user = datos.imap_user
    cfg.imap_folder = datos.imap_folder
    cfg.poll_minutos = datos.poll_minutos
    cfg.remitentes_permitidos = datos.remitentes_permitidos or None
    cfg.auto_activo = datos.auto_activo
    cfg.confirmaciones_activas = datos.confirmaciones_activas
    db.commit()
    db.refresh(cfg)

    audit.log(db, username=user.username, rol=user.rol, accion="UPDATE",
              recurso="configuracion_correo",
              detalle=f"host={cfg.imap_host} auto={cfg.auto_activo} poll={cfg.poll_minutos}")

    return ConfigCorreoOut(
        imap_host=cfg.imap_host, imap_port=cfg.imap_port, imap_user=cfg.imap_user,
        imap_folder=cfg.imap_folder, poll_minutos=cfg.poll_minutos,
        remitentes_permitidos=cfg.remitentes_permitidos, auto_activo=cfg.auto_activo,
        confirmaciones_activas=cfg.confirmaciones_activas,
        password_configurado=password_configurado(),
    )
