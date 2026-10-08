from src.api.v1.auth.schemas import LoginRequest
from src.core.security.hashing import verify_password
from src.core.security.jwt import create_access_token
from src.infrastructure.repositories.user_repository import UserRepository


class AuthService:

    def __init__(
        self,
        repository: UserRepository
    ):
        self.repository = repository

    async def login(
        self,
        request: LoginRequest
    ) -> str:
        user = await self.repository.get_by_email(
            request.correo
        )

        if not user or not verify_password(
            request.contrasena,
            user.contrasena
        ):
            raise ValueError(
                "Correo o contraseña incorrectos"
            )

        return create_access_token(
            user_id=user.id,
            rol=user.rol
        )
