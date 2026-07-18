from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "bbva_interno"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    RFC_RECEPTOR: str = "EOL060201JC8"
    NOMBRE_RECEPTOR: str = "E-FARMA ON LINE"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str
    FRONTEND_URL: str = "http://localhost:3000"
    MAX_UPLOAD_MB: int = 10
    # Margen de redondeo (en pesos) al cotejar montos contra fórmulas y layout.
    # Absoluto; definir con el área fiscal si debe ser relativo.
    TOLERANCIA_MONTO: float = 0.10

    # IMAP — correo de honorarios
    IMAP_HOST: str = "imap.gmail.com"
    IMAP_PORT: int = 993
    IMAP_USER: str = "honorarios@thehumantalent.com"
    IMAP_PASSWORD: Optional[str] = None   # App Password de Google
    IMAP_FOLDER: str = "INBOX"
    IMAP_POLL_MINUTES: int = 5            # intervalo de revisión automática

    class Config:
        env_file = ".env"


settings = Settings()
