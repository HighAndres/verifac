import uuid
from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), nullable=False)
    rol = Column(String(20))
    accion = Column(String(50), nullable=False)     # LOGIN, CREATE, UPDATE, DELETE, UPLOAD
    recurso = Column(String(50))                    # factura, profesor, usuario, catalogo...
    recurso_id = Column(String(100))
    detalle = Column(Text)
    ip = Column(String(50))
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
