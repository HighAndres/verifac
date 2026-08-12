"""Utilidades para normalizar y validar correos usados como credencial de login."""
import re

_RE_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Dominio de correos placeholder (`<rfc>@pendiente.local`): son marcadores, no
# correos reales, y NO deben servir como credencial de acceso.
PLACEHOLDER_DOMINIO = "@pendiente.local"


def normalizar_correo(valor: str | None) -> str | None:
    """Recorta espacios y pasa a minúsculas; devuelve None si queda vacío."""
    if valor is None:
        return None
    v = valor.strip().lower()
    return v or None


def es_correo_valido(valor: str | None) -> bool:
    return bool(valor) and bool(_RE_CORREO.match(valor))


def es_placeholder(valor: str | None) -> bool:
    """True si el correo es un marcador `@pendiente.local` (no sirve para login)."""
    return bool(valor) and valor.lower().endswith(PLACEHOLDER_DOMINIO)
