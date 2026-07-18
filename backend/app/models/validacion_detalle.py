from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.db.base_class import Base

class ValidacionDetalle(Base):
    __tablename__ = "validacion_detalle"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    factura_id = Column(UUID(as_uuid=True), ForeignKey("facturas.id"), nullable=False)
    campo = Column(String(100), nullable=False)
    valor_recibido = Column(String(500))
    valor_esperado = Column(String(500))
    resultado = Column(Boolean, nullable=False)
    mensaje = Column(String(500))
