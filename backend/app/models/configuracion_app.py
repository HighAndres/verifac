from sqlalchemy import Boolean, Column, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.base_class import Base


class ConfiguracionApp(Base):
    """Interruptores globales del sistema (fila única)."""
    __tablename__ = "configuracion_app"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Si está apagado, el portal rechaza POST /portal/subir-factura — no afecta
    # la carga manual de un revisor/superadmin ni el correo.
    carga_xml_portal_activa = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
