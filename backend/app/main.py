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
    from app.services.imap_watcher import revisar_correo
    from app.db.session import SessionLocal

    intervalo = settings.IMAP_POLL_MINUTES * 60
    logger.info("Watcher IMAP iniciado — cada %d min", settings.IMAP_POLL_MINUTES)

    while True:
        await asyncio.sleep(intervalo)
        if not settings.IMAP_PASSWORD or settings.IMAP_PASSWORD == "pon-aqui-tu-app-password":
            continue
        db = SessionLocal()
        try:
            r = revisar_correo(db, settings.IMAP_HOST, settings.IMAP_PORT,
                               settings.IMAP_USER, settings.IMAP_PASSWORD, settings.IMAP_FOLDER)
            if r.get("total_procesadas") or r.get("total_errores"):
                logger.info("Watcher: %d procesadas, %d errores",
                            r["total_procesadas"], r["total_errores"])
        except Exception:
            logger.exception("Error en el ciclo del watcher IMAP")
        finally:
            db.close()


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
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {"project": settings.PROJECT_NAME, "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}
