from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # Ej: "http://localhost:5173,https://church-connect.app"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # SMTP: envío de correos (notificaciones, etc.). Si `SMTP_HOST` o
    # `SMTP_FROM` quedan vacíos, el envío se omite (ver `smtp_configured`).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_FROM)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()