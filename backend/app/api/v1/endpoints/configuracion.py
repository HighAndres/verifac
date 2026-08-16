from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_db, require_superadmin
from app.models.usuario import Usuario
from app.services import audit
from app.services.config_app import obtener_config_app

router = APIRouter()


class CargaXmlOut(BaseModel):
    carga_xml_portal_activa: bool

    model_config = {"from_attributes": True}


class CargaXmlIn(BaseModel):
    carga_xml_portal_activa: bool


@router.get("/carga-xml", response_model=CargaXmlOut)
def obtener_carga_xml(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_superadmin),
):
    return obtener_config_app(db)


@router.put("/carga-xml", response_model=CargaXmlOut)
def actualizar_carga_xml(
    datos: CargaXmlIn,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_superadmin),
):
    cfg = obtener_config_app(db)
    cfg.carga_xml_portal_activa = datos.carga_xml_portal_activa
    audit.log(db, username=user.username, rol=user.rol, accion="UPDATE",
              recurso="configuracion_app",
              detalle=f"Carga de XML del portal → {'activada' if datos.carga_xml_portal_activa else 'desactivada'}",
              ip=get_client_ip(request))
    db.commit()
    db.refresh(cfg)
    return cfg
