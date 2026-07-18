from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CatalogoClaveBase(BaseModel):
    clave: str
    descripcion: str
    tipo: str  # "servicio" | "unidad"
    activo: bool = True


class CatalogoClaveCreate(CatalogoClaveBase):
    pass


class CatalogoClaveUpdate(BaseModel):
    descripcion: Optional[str] = None
    tipo: Optional[str] = None
    activo: Optional[bool] = None


class CatalogoClaveOut(CatalogoClaveBase):
    id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
