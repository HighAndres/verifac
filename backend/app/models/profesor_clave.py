from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy import Column
from app.db.base_class import Base

class ProfesorClave(Base):
    __tablename__ = "profesor_claves"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profesor_id = Column(UUID(as_uuid=True), ForeignKey("profesores.id"), nullable=False)
    catalogo_clave_id = Column(UUID(as_uuid=True), ForeignKey("catalogo_claves.id"), nullable=False)
