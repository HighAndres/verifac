from fastapi import APIRouter, Depends

from app.api.deps import require_revisor, require_superadmin
from app.api.v1.endpoints import (
    auth, auditoria, catalogo_claves, dashboard, facturas,
    profesor_claves, profesores, usuarios, watcher,
)

api_router = APIRouter()

# Público
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Revisor o superadmin
_rev = {"dependencies": [Depends(require_revisor)]}
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"], **_rev)
api_router.include_router(profesores.router, prefix="/profesores", tags=["profesores"], **_rev)
api_router.include_router(profesor_claves.router, prefix="/profesores", tags=["profesor → claves"], **_rev)
api_router.include_router(catalogo_claves.router, prefix="/catalogo-claves", tags=["catálogo de claves"], **_rev)
api_router.include_router(facturas.router, prefix="/facturas", tags=["facturas"], **_rev)
api_router.include_router(watcher.router, prefix="/watcher", tags=["watcher IMAP"], **_rev)

# Solo superadmin
_adm = {"dependencies": [Depends(require_superadmin)]}
api_router.include_router(usuarios.router, prefix="/usuarios", tags=["usuarios"], **_adm)
api_router.include_router(auditoria.router, prefix="/auditoria", tags=["auditoría"], **_adm)
