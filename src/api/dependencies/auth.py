from datetime import UTC
from uuid import UUID

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.participaciones import get_email_service
from src.application.auth.password_reset import PasswordResetService
from src.application.auth.services import AuthService
from src.infrastructure.email.email_service import EmailService
from src.core.security.jwt import decode_access_token
from src.infrastructure.database.models.user_model import UserModel
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.user_repository import UserRepository

# HTTPBearer en vez de OAuth2PasswordBearer: el botón "Authorize" de Swagger
# pide pegar el token directamente (sin disparar una petición AJAX propia),
# evitando bugs de swagger-ui con el flujo OAuth2 password en algunos entornos.
bearer_scheme = HTTPBearer()


def get_password_reset_service(
    db: AsyncSession = Depends(get_db),
    mailer: EmailService = Depends(get_email_service)
) -> PasswordResetService:
    return PasswordResetService(db, mailer)


def get_auth_service(
    db: AsyncSession = Depends(get_db)
) -> AuthService:
    repository = UserRepository(db)

    return AuthService(repository)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> UserModel:
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la credencial",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
    except (ValueError, KeyError):
        raise credentials_exception

    repository = UserRepository(db)
    user = await repository.get_by_id(user_id)

    if not user:
        raise credentials_exception

    # Tras restablecer la contraseña, las sesiones abiertas antes dejan de
    # valer: su token se emitió antes del cambio (o no dice cuándo).
    if user.contrasena_cambiada_en is not None:
        cambiada = user.contrasena_cambiada_en
        if cambiada.tzinfo is None:
            cambiada = cambiada.replace(tzinfo=UTC)

        emitido = payload.get("iat")
        if not isinstance(emitido, (int, float)) or emitido < int(cambiada.timestamp()):
            raise credentials_exception

    return user
