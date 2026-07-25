"""Ejecuta el watcher IMAP de forma segura: una sola revisión a la vez (lock) y
guarda un resumen del último resultado para que la UI lo consulte. Lo usan tanto
el botón manual (en segundo plano) como el poll automático.

Motivo: procesar muchos correos tarda más que el timeout del proxy; correrlo en
segundo plano evita que el botón "parezca" que falla, y el lock evita que el
manual y el automático choquen.
"""
import logging
import threading
from datetime import datetime, timezone

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.config_correo import obtener_config, password_configurado, remitentes_lista
from app.services.imap_watcher import revisar_correo

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_estado: dict = {
    "running": False,
    "iniciado": None,
    "terminado": None,
    "ultimo": None,   # resumen compacto del último run
}


def estado() -> dict:
    return dict(_estado)


def run_once(origen: str = "manual") -> dict:
    """Corre una revisión si no hay otra en curso. Idempotente frente a concurrencia."""
    if not password_configurado():
        return {"ok": False, "error": "Correo no configurado"}
    if not _lock.acquire(blocking=False):
        return {"ok": False, "running": True, "mensaje": "Ya hay una revisión en curso"}

    _estado["running"] = True
    _estado["iniciado"] = datetime.now(timezone.utc).isoformat()
    try:
        db = SessionLocal()
        try:
            cfg = obtener_config(db)
            r = revisar_correo(
                db, cfg.imap_host, cfg.imap_port, cfg.imap_user,
                settings.IMAP_PASSWORD, cfg.imap_folder, remitentes_lista(cfg),
            )
        finally:
            db.close()
        _estado["ultimo"] = {
            "revisados": r.get("revisados", 0),
            "procesadas": r.get("total_procesadas", 0),
            "errores": r.get("total_errores", 0),
            "omitidos": r.get("omitidos", 0),
            "origen": origen,
            "timestamp": r.get("timestamp"),
        }
        logger.info("Watcher (%s): %s procesadas, %s errores", origen,
                    r.get("total_procesadas"), r.get("total_errores"))
        return r
    except Exception:
        logger.exception("Error en la revisión del watcher")
        _estado["ultimo"] = {"error": "Falló la revisión", "origen": origen,
                             "timestamp": datetime.now(timezone.utc).isoformat()}
        return {"ok": False, "error": "Falló la revisión"}
    finally:
        _estado["running"] = False
        _estado["terminado"] = datetime.now(timezone.utc).isoformat()
        _lock.release()
