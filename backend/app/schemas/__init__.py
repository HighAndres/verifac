from app.schemas.profesor import ProfesorCreate, ProfesorUpdate, ProfesorOut, ProfesorListOut
from app.schemas.catalogo_clave import CatalogoClaveCreate, CatalogoClaveUpdate, CatalogoClaveOut
from app.schemas.factura import FacturaOut, FacturaDetalleOut, FacturaListOut, ValidacionDetalleOut

__all__ = [
    "ProfesorCreate", "ProfesorUpdate", "ProfesorOut", "ProfesorListOut",
    "CatalogoClaveCreate", "CatalogoClaveUpdate", "CatalogoClaveOut",
    "FacturaOut", "FacturaDetalleOut", "FacturaListOut", "ValidacionDetalleOut",
]
