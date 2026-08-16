"""Acceso a los interruptores globales del sistema (fila única)."""
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.configuracion_app import ConfiguracionApp

# ID fijo de la fila única: si dos procesos intentan crearla a la vez, chocan en la
# PK y solo una gana (la otra la relee), evitando filas duplicadas por carrera.
SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def obtener_config_app(db: Session) -> ConfiguracionApp:
    """Devuelve la config; si no existe, la crea con los valores por defecto."""
    cfg = db.query(ConfiguracionApp).order_by(ConfiguracionApp.updated_at).first()
    if cfg is not None:
        return cfg

    cfg = ConfiguracionApp(id=SINGLETON_ID, carga_xml_portal_activa=True)
    db.add(cfg)
    try:
        db.commit()
    except IntegrityError:          # otro proceso la creó primero
        db.rollback()
        return db.query(ConfiguracionApp).order_by(ConfiguracionApp.updated_at).first()
    db.refresh(cfg)
    return cfg
