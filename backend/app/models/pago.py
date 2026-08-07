import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base_class import Base


class Pago(Base):
    """Registro de pago a un profesor por mes/año.

    Es una entidad mensual independiente de la factura: la granularidad es
    profesor+periodo y no se apoya en `montos_mensuales` (que se recarga).
    """
    __tablename__ = "pagos"
    __table_args__ = (UniqueConstraint("profesor_id", "mes", "anio", name="uq_pago_profesor_periodo"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profesor_id = Column(UUID(as_uuid=True), ForeignKey("profesores.id"), nullable=False, index=True)
    mes = Column(Integer, nullable=False)
    anio = Column(Integer, nullable=False)
    pagada = Column(Boolean, default=False, nullable=False)
    fecha_pago = Column(Date, nullable=True)
    metodo_pago = Column(String(40), nullable=True)
    incidencia = Column(String(40), nullable=True)   # motivo de retraso, independiente de `pagada`
    registrado_por = Column(String(50), nullable=True)   # username del revisor que marcó
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
