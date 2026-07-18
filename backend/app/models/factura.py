from sqlalchemy import Column, String, Numeric, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.base_class import Base

class Factura(Base):
    __tablename__ = "facturas"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uuid_cfdi = Column(String(36), unique=True, nullable=False, index=True)
    rfc_emisor = Column(String(13), nullable=False, index=True)
    nombre_emisor = Column(String(200))
    regimen_emisor = Column(String(3))
    rfc_receptor = Column(String(13))
    nombre_receptor = Column(String(200))
    moneda = Column(String(3))
    fecha_emision = Column(DateTime(timezone=True))
    fecha_timbrado = Column(DateTime(timezone=True))
    subtotal = Column(Numeric(12, 2))
    iva_trasladado = Column(Numeric(12, 2))
    iva_retenido = Column(Numeric(12, 2))
    isr_retenido = Column(Numeric(12, 2))
    total = Column(Numeric(12, 2))
    clave_servicio = Column(String(20))
    clave_unidad = Column(String(20))
    descripcion_concepto = Column(Text)
    forma_pago = Column(String(3))
    metodo_pago = Column(String(3))
    uso_cfdi = Column(String(5))
    estado = Column(String(20), default="pendiente")
    motivo_rechazo = Column(Text)
    fecha_validacion = Column(DateTime(timezone=True))
    origen = Column(String(20), default="xml", nullable=False)   # xml | captura_manual
    pdf_cotejo = Column(String(20))                              # ok | no_coincide | sin_pdf
    created_at = Column(DateTime(timezone=True), server_default=func.now())
