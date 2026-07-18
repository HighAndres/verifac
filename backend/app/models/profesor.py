from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.base_class import Base

class Profesor(Base):
    __tablename__ = "profesores"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rfc = Column(String(13), unique=True, nullable=False, index=True)
    nombre = Column(String(200), nullable=False)
    correo = Column(String(200), nullable=False)
    regimen_fiscal = Column(String(3), nullable=False)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
