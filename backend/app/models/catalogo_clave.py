from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.base_class import Base

class CatalogoClave(Base):
    __tablename__ = "catalogo_claves"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clave = Column(String(20), unique=True, nullable=False, index=True)
    descripcion = Column(String(300), nullable=False)
    tipo = Column(String(20), nullable=False)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
