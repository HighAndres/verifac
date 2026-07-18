from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.db.base_class import Base


class ConfiguracionCorreo(Base):
    """Configuración editable del watcher IMAP (fila única). La contraseña NO se
    guarda aquí: vive en el .env por seguridad."""
    __tablename__ = "configuracion_correo"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imap_host = Column(String(200), nullable=False)
    imap_port = Column(Integer, nullable=False, default=993)
    imap_user = Column(String(200), nullable=False)
    imap_folder = Column(String(100), nullable=False, default="INBOX")
    poll_minutos = Column(Integer, nullable=False, default=5)
    # Coma-separado. Vacío = procesar correos de cualquier remitente.
    remitentes_permitidos = Column(Text, nullable=True)
    auto_activo = Column(Boolean, nullable=False, default=True)
    # Enviar correo de confirmación al profesor cuando su factura queda aprobada.
    confirmaciones_activas = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
