from sqlalchemy import Column, String, Numeric, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.base_class import Base


class MontoMensual(Base):
    __tablename__ = "montos_mensuales"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profesor_id = Column(UUID(as_uuid=True), ForeignKey("profesores.id"), nullable=True, index=True)
    nombre_layout = Column(String(200), nullable=False)
    rfc_emisor = Column(String(13), nullable=True, index=True)
    regimen_fiscal = Column(String(3), nullable=False)
    categoria = Column(String(100), nullable=True)
    mes = Column(Integer, nullable=False)
    anio = Column(Integer, nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)
    iva_trasladado = Column(Numeric(12, 2), nullable=False, default=0)
    iva_retenido = Column(Numeric(12, 2), nullable=False, default=0)
    isr_retenido = Column(Numeric(12, 2), nullable=False, default=0)
    total = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
