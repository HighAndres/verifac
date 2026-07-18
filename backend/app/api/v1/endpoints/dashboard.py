from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.dashboard import resumen_mes

router = APIRouter()


@router.get("", summary="Dashboard del mes: facturas, montos y pendientes")
def panorama(
    mes: int = Query(..., ge=1, le=12),
    anio: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
):
    return resumen_mes(db, mes, anio)
