"""Acceso a la configuración del watcher IMAP (fila única, con semilla del .env)."""
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.configuracion_correo import ConfiguracionCorreo

# ID fijo de la fila única: si dos procesos intentan crearla a la vez, chocan en la
# PK y solo una gana (la otra la relee), evitando filas duplicadas por carrera.
SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def obtener_config(db: Session) -> ConfiguracionCorreo:
    """Devuelve la config; si no existe, la crea con los valores del .env."""
    # order_by determinista: si existieran filas previas, siempre se lee la misma.
    cfg = db.query(ConfiguracionCorreo).order_by(ConfiguracionCorreo.updated_at).first()
    if cfg is not None:
        return cfg

    cfg = ConfiguracionCorreo(
        id=SINGLETON_ID,
        imap_host=settings.IMAP_HOST,
        imap_port=settings.IMAP_PORT,
        imap_user=settings.IMAP_USER,
        imap_folder=settings.IMAP_FOLDER,
        poll_minutos=settings.IMAP_POLL_MINUTES,
        auto_activo=True,
    )
    db.add(cfg)
    try:
        db.commit()
    except IntegrityError:          # otro proceso la creó primero
        db.rollback()
        return db.query(ConfiguracionCorreo).order_by(ConfiguracionCorreo.updated_at).first()
    db.refresh(cfg)
    return cfg


def remitentes_lista(cfg: ConfiguracionCorreo) -> list[str]:
    """Lista normalizada (minúsculas) de remitentes permitidos. Vacía = todos."""
    if not cfg.remitentes_permitidos:
        return []
    crudo = cfg.remitentes_permitidos.replace("\n", ",").replace(";", ",")
    return [r.strip().lower() for r in crudo.split(",") if r.strip()]


def password_configurado() -> bool:
    return bool(
        settings.IMAP_PASSWORD
        and settings.IMAP_PASSWORD != "pon-aqui-tu-app-password"
    )
