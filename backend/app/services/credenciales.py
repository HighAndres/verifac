"""Generación y envío de credenciales de acceso para profesores.

Crea cuentas (rol "profesor") en lote para los profesores activos con correo
real que aún no tienen una, y envía la contraseña por correo. La contraseña
solo viaja en ese correo: si el envío falla, la cuenta recién creada se
revierte para no dejar credenciales que nadie conoce.

También regenera y reenvía la contraseña de una cuenta existente (es la vía de
"recuperación" mientras no exista autoservicio): se cambia el hash y se envía
la nueva contraseña; si el correo falla, el caller NO debe comitear, con lo que
la contraseña anterior sigue vigente.
"""
import logging
import secrets
import smtplib

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.emails import es_correo_valido, es_placeholder, normalizar_correo
from app.core.security import hash_password
from app.models.profesor import Profesor
from app.models.usuario import Usuario
from app.services.email_confirmacion import enviar_smtp

logger = logging.getLogger(__name__)

# Sin caracteres ambiguos (0/O, 1/l/I): la contraseña llega por correo y a
# veces se transcribe a mano.
_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"


def generar_password(longitud: int = 12) -> str:
    return "".join(secrets.choice(_ALFABETO) for _ in range(longitud))


def _cuerpo_credenciales(nombre: str, correo: str, password: str) -> tuple[str, str]:
    asunto = "Tu acceso al portal de facturas Verifac"
    cuerpo = f"""Estimado(a) {nombre}:

Se generó tu acceso al portal de facturas Verifac. Ahí puedes subir tu
factura de cada mes y consultar su estado.

    Portal:      {settings.FRONTEND_URL}
    Usuario:     {correo}   (tu correo)
    Contraseña:  {password}

Guarda esta contraseña en un lugar seguro. Si la pierdes, solicita al
administrador que te envíe una nueva.

Este es un mensaje automático de Verifac; por favor no responda a este correo.
"""
    return asunto, cuerpo


def _username_libre(db: Session, base: str) -> str:
    username = base
    n = 2
    while db.query(Usuario).filter(Usuario.username == username).first():
        username = f"{base}{n}"
        n += 1
    return username


def generar_credenciales_profesores(db: Session) -> dict:
    """Crea y envía credenciales a todos los profesores activos sin cuenta.

    Por cada profesor: cuenta nueva rol "profesor" (username = RFC en
    minúsculas, login por correo) con contraseña aleatoria, enviada a su
    correo. Commit por profesor; si el envío falla se revierte ESA cuenta.
    Un fallo de conexión/autenticación corta el lote (los demás fallarían igual).
    """
    con_cuenta = {
        u.profesor_id
        for u in db.query(Usuario).filter(Usuario.profesor_id.isnot(None)).all()
    }

    creados: list[dict] = []
    errores: list[dict] = []
    omitidos: list[dict] = []

    profesores = (
        db.query(Profesor)
        .filter(Profesor.activo == True)  # noqa: E712
        .order_by(Profesor.nombre)
        .all()
    )

    for p in profesores:
        if p.id in con_cuenta:
            continue

        # Copia local: tras commit/rollback el objeto queda expirado.
        nombre, rfc = p.nombre, p.rfc
        correo = normalizar_correo(p.correo)

        if not correo or not es_correo_valido(correo) or es_placeholder(correo):
            omitidos.append({"nombre": nombre, "rfc": rfc,
                             "motivo": "sin correo real capturado"})
            continue
        if db.query(Usuario).filter(func.lower(Usuario.correo) == correo).first():
            omitidos.append({"nombre": nombre, "rfc": rfc,
                             "motivo": f"el correo {correo} ya está en uso por otra cuenta"})
            continue

        password = generar_password()
        user = Usuario(
            username=_username_libre(db, rfc.lower()),
            nombre=nombre,
            correo=correo,
            password_hash=hash_password(password),
            rol="profesor",
            profesor_id=p.id,
        )
        db.add(user)
        db.flush()

        try:
            asunto, cuerpo = _cuerpo_credenciales(nombre, correo, password)
            enviar_smtp(correo, asunto, cuerpo)
            db.commit()
            creados.append({"nombre": nombre, "rfc": rfc, "correo": correo})
            logger.info("Credenciales enviadas a %s (%s)", correo, rfc)
        except smtplib.SMTPRecipientsRefused:
            db.rollback()
            errores.append({"nombre": nombre, "rfc": rfc,
                            "motivo": f"el correo {correo} fue rechazado por el servidor"})
            logger.exception("Destinatario rechazado para %s; se continúa", rfc)
        except Exception:
            # Fallo de conexión/autenticación: los demás envíos fallarían igual.
            db.rollback()
            errores.append({"nombre": nombre, "rfc": rfc,
                            "motivo": "fallo de conexión con el servidor de correo; se detuvo el lote"})
            logger.exception("No se pudieron enviar credenciales de %s; se detiene el lote", rfc)
            break

    return {
        "creados": len(creados),
        "errores": len(errores),
        "omitidos": len(omitidos),
        "detalle_creados": creados,
        "detalle_errores": errores,
        "detalle_omitidos": omitidos,
    }


def regenerar_y_enviar(db: Session, user: Usuario) -> str:
    """Genera una contraseña nueva para la cuenta y la envía a su correo.
    Devuelve el correo destino. NO comitea: si el envío truena, el caller debe
    hacer rollback y la contraseña anterior sigue vigente."""
    correo = normalizar_correo(user.correo)
    if not correo or not es_correo_valido(correo) or es_placeholder(correo):
        raise ValueError("La cuenta no tiene un correo real al cual enviar las credenciales")

    password = generar_password()
    user.password_hash = hash_password(password)
    asunto, cuerpo = _cuerpo_credenciales(user.nombre, correo, password)
    enviar_smtp(correo, asunto, cuerpo)
    return correo
