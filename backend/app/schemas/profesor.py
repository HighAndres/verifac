import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

_RFC_RE = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")


class ProfesorBase(BaseModel):
    rfc: str
    nombre: str
    correo: str
    regimen_fiscal: str

    @field_validator("rfc")
    @classmethod
    def rfc_valido(cls, v: str) -> str:
        v = v.strip().upper()
        if not _RFC_RE.match(v):
            raise ValueError("RFC inválido — formato esperado: AAA000000AA0 (persona moral) o AAAA000000AA0 (persona física)")
        return v

    @field_validator("regimen_fiscal")
    @classmethod
    def regimen_valido(cls, v: str) -> str:
        if v not in {"626", "612", "603"}:
            raise ValueError("regimen_fiscal debe ser 626, 612 o 603")
        return v


class ProfesorCreate(ProfesorBase):
    pass


class ProfesorUpdate(BaseModel):
    nombre: Optional[str] = None
    correo: Optional[str] = None
    regimen_fiscal: Optional[str] = None
    activo: Optional[bool] = None


class ProfesorOut(ProfesorBase):
    id: UUID
    activo: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfesorListOut(BaseModel):
    total: int
    items: list[ProfesorOut]
