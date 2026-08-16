from fastapi import APIRouter, Depends

from app.api.deps import require_lectura, require_profesor, require_revisor, require_superadmin
from app.api.v1.endpoints import (
    auth, auditoria, catalogo_claves, configuracion, dashboard, facturas,
    pagos, portal, profesor_claves, profesores, usuarios, watcher,
)

api_router = APIRouter()

# Público
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Portal del profesor (rol profesor)
api_router.include_router(
    portal.router, prefix="/portal", tags=["portal profesor"],
    dependencies=[Depends(require_profesor)],
)

# Revisor o superadmin (sin acceso para 'consulta')
_rev = {"dependencies": [Depends(require_revisor)]}
api_router.include_router(watcher.router, prefix="/watcher", tags=["watcher IMAP"], **_rev)
api_router.include_router(profesores.router, prefix="/profesores", tags=["profesores"], **_rev)
api_router.include_router(profesor_claves.router, prefix="/profesores", tags=["profesor → claves"], **_rev)
api_router.include_router(catalogo_claves.router, prefix="/catalogo-claves", tags=["catálogo de claves"], **_rev)
api_router.include_router(pagos.router, prefix="/pagos", tags=["pagos"], **_rev)

# Revisor, superadmin o consulta (lectura) — 'consulta' solo ve el dashboard y
# descarga el Excel de reportes (facturas/export-mes). El resto de endpoints de
# facturas (listar, detalle, montos) se re-protegen individualmente con
# require_revisor dentro de facturas.py; los de escritura ya lo estaban.
_lec = {"dependencies": [Depends(require_lectura)]}
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"], **_lec)
api_router.include_router(facturas.router, prefix="/facturas", tags=["facturas"], **_lec)

# Solo superadmin
_adm = {"dependencies": [Depends(require_superadmin)]}
api_router.include_router(usuarios.router, prefix="/usuarios", tags=["usuarios"], **_adm)
api_router.include_router(auditoria.router, prefix="/auditoria", tags=["auditoría"], **_adm)
api_router.include_router(configuracion.router, prefix="/configuracion", tags=["configuración"], **_adm)
