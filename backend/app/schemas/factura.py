from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ValidacionDetalleOut(BaseModel):
    id: UUID
    campo: str
    valor_recibido: Optional[str] = None
    valor_esperado: Optional[str] = None
    resultado: bool
    mensaje: Optional[str] = None

    model_config = {"from_attributes": True}


class FacturaOut(BaseModel):
    id: UUID
    uuid_cfdi: str
    rfc_emisor: str
    nombre_emisor: Optional[str] = None
    regimen_emisor: Optional[str] = None
    fecha_emision: Optional[datetime] = None
    fecha_timbrado: Optional[datetime] = None
    subtotal: Optional[Decimal] = None
    iva_trasladado: Optional[Decimal] = None
    iva_retenido: Optional[Decimal] = None
    isr_retenido: Optional[Decimal] = None
    total: Optional[Decimal] = None
    clave_servicio: Optional[str] = None
    clave_unidad: Optional[str] = None
    descripcion_concepto: Optional[str] = None
    forma_pago: Optional[str] = None
    metodo_pago: Optional[str] = None
    uso_cfdi: Optional[str] = None
    estado: str
    motivo_rechazo: Optional[str] = None
    fecha_validacion: Optional[datetime] = None
    origen: Optional[str] = None
    pdf_cotejo: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FacturaDetalleOut(FacturaOut):
    detalles: list[ValidacionDetalleOut] = []


class FacturaListOut(BaseModel):
    total: int
    items: list[FacturaOut]
