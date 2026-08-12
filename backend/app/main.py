import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router

logger = logging.getLogger(__name__)


def _bootstrap_superadmin():
    """Crea el primer superadmin desde .env si la tabla de usuarios está vacía."""
    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.models.usuario import Usuario

    db = SessionLocal()
    try:
        if db.query(Usuario).count() == 0:
            admin = Usuario(
                username=settings.ADMIN_USERNAME,
                nombre="Super Admin",
                correo=settings.ADMIN_EMAIL.strip().lower(),
                password_hash=settings.ADMIN_PASSWORD_HASH,
                rol="superadmin",
            )
            db.add(admin)
            db.commit()
            logger.info("Superadmin '%s' creado desde .env", settings.ADMIN_USERNAME)
    except Exception:
        logger.exception("Error al crear superadmin inicial")
        db.rollback()
    finally:
        db.close()


async def _poll_loop():
    from app.services import watcher_runner
    from app.services.config_correo import obtener_config
    from app.db.session import SessionLocal

    logger.info("Watcher IMAP iniciado (config editable desde la BD)")

    while True:
        # Leer la config vigente en cada ciclo (intervalo, on/off).
        db = SessionLocal()
        try:
            cfg = obtener_config(db)
            intervalo = max(1, cfg.poll_minutos) * 60
            activo = cfg.auto_activo
        except Exception:
            logger.exception("No se pudo leer la config de correo")
            intervalo, activo = 300, False
        finally:
            db.close()

        await asyncio.sleep(intervalo)

        if not activo:
            continue

        # run_once corre en un hilo (imaplib es bloqueante) y respeta el lock
        # compartido: si el botón manual ya está corriendo, este ciclo se salta.
        try:
            await asyncio.to_thread(watcher_runner.run_once, "auto")
        except Exception:
            logger.exception("Error en el ciclo del watcher IMAP")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _bootstrap_superadmin()
    task = asyncio.create_task(_poll_loop())
    yield
    task.cancel()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {"project": settings.PROJECT_NAME, "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}
