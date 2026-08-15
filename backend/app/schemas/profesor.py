import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

_RFC_RE = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")


def _validar_drive_url(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if not v.startswith(("http://", "https://")):
        raise ValueError("drive_url debe ser una URL http(s)")
    return v


def _validar_regimen(v: Optional[str]) -> Optional[str]:
    if v is not None and v not in {"626", "612", "603"}:
        raise ValueError("regimen_fiscal debe ser 626, 612 o 603")
    return v


class ProfesorBase(BaseModel):
    rfc: str
    nombre: str
    correo: str
    regimen_fiscal: str
    drive_url: Optional[str] = None

    @field_validator("drive_url")
    @classmethod
    def drive_url_valido(cls, v: Optional[str]) -> Optional[str]:
        return _validar_drive_url(v)

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
        return _validar_regimen(v)


class ProfesorCreate(ProfesorBase):
    pass


class ProfesorUpdate(BaseModel):
    nombre: Optional[str] = None
    correo: Optional[str] = None
    regimen_fiscal: Optional[str] = None
    drive_url: Optional[str] = None
    activo: Optional[bool] = None

    @field_validator("drive_url")
    @classmethod
    def drive_url_valido(cls, v: Optional[str]) -> Optional[str]:
        return _validar_drive_url(v)

    @field_validator("regimen_fiscal")
    @classmethod
    def regimen_valido(cls, v: Optional[str]) -> Optional[str]:
        return _validar_regimen(v)


class ProfesorOut(ProfesorBase):
    id: UUID
    activo: bool
    created_at: datetime
    tiene_cuenta: bool = False
    cuenta_username: Optional[str] = None

    model_config = {"from_attributes": True}


class ProfesorListOut(BaseModel):
    total: int
    items: list[ProfesorOut]
