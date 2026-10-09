from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valores de `ENVIRONMENT` que se consideran desarrollo.
DEV_ENVIRONMENTS = {"local", "development", "dev"}

# Orígenes que se usan en desarrollo cuando `CORS_ORIGINS` no está definido.
DEV_CORS_ORIGINS = "http://localhost:5173,http://localhost:3000"

LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _is_local_origin(origin: str) -> bool:
    # Sin esquema ("localhost:5173") urlsplit no detecta el host.
    host = urlsplit(origin if "://" in origin else f"//{origin}").hostname or ""
    return host in LOCAL_HOSTS or host.endswith(".localhost")


class Settings(BaseSettings):
    APP_NAME: str
    API_VERSION: str
    DEBUG: bool
    ENVIRONMENT: str

    # Environment variables for database connection
    DATABASE_URL: str

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS: orígenes permitidos para el frontend, separados por comas.
    # Ej: "https://church-connect.app,https://admin.church-connect.app"
    # Sin valor fijo: en ambientes de desarrollo (ver `is_development`) se
    # completa con `DEV_CORS_ORIGINS` si queda vacío; en cualquier otro
    # ambiente es obligatorio y no admite orígenes locales ni el comodín "*".
    CORS_ORIGINS: str = ""

    # SMTP: envío de correos (notificaciones, etc.). Si `MAIL_SMTP_HOST` o
    # `MAIL_SMTP_FROM` quedan vacíos, el envío se omite (ver `smtp_configured`).
    MAIL_SMTP_HOST: str = ""
    MAIL_SMTP_PORT: int = 587
    MAIL_SMTP_USERNAME: str = ""
    MAIL_SMTP_PASSWORD: str = ""
    MAIL_SMTP_FROM: str = ""

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in DEV_ENVIRONMENTS

    @model_validator(mode="after")
    def validate_cors_origins(self) -> "Settings":
        if self.is_development:
            if not self.cors_origins_list:
                self.CORS_ORIGINS = DEV_CORS_ORIGINS
            return self

        if not self.cors_origins_list:
            raise ValueError(
                f"CORS_ORIGINS es obligatorio cuando ENVIRONMENT="
                f"'{self.ENVIRONMENT}' (solo se omite en: "
                f"{', '.join(sorted(DEV_ENVIRONMENTS))})."
            )

        forbidden = [
            origin for origin in self.cors_origins_list
            if origin == "*" or _is_local_origin(origin)
        ]
        if forbidden:
            raise ValueError(
                f"CORS_ORIGINS no admite orígenes locales ni '*' cuando "
                f"ENVIRONMENT='{self.ENVIRONMENT}': {', '.join(forbidden)}"
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.MAIL_SMTP_HOST and self.MAIL_SMTP_FROM)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()