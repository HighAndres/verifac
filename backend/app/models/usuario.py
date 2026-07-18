import uuid
from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base_class import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    nombre = Column(String(200), nullable=False)
    password_hash = Column(String(200), nullable=False)
    rol = Column(String(20), nullable=False)        # superadmin | revisor
    activo = Column(Boolean, default=True, nullable=False)
    ultimo_acceso = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
