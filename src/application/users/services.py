from datetime import datetime, UTC
from uuid import UUID
from uuid import uuid4

from src.api.v1.users.schemas import UserCreate
from src.api.v1.users.schemas import UserUpdate
from src.core.security.hashing import hash_password
from src.infrastructure.database.models.user_model import UserModel
from src.infrastructure.repositories.user_repository import UserRepository


class UserService:

    def __init__(
        self,
        repository: UserRepository
    ):
        self.repository = repository

    async def get_all(
        self,
        limit: int,
        offset: int
    ):
        return await self.repository.get_all(
            limit=limit,
            offset=offset
        )

    async def count(self) -> int:
        return await self.repository.count()

    async def get_by_id(
        self,
        user_id: UUID
    ):
        user = await self.repository.get_by_id(user_id)

        if not user:
            raise ValueError("Usuario no encontrado")

        return user

    async def create(
        self,
        request: UserCreate
    ):
        existing_user = await self.repository.get_by_email(
            request.correo
        )

        if existing_user:
            raise ValueError(
                "El correo ya se encuentra registrado"
            )

        user = UserModel(
            id=uuid4(),
            nombre=request.nombre,
            apellido=request.apellido,
            correo=request.correo,
            contrasena=hash_password(request.contrasena),
            telefono=request.telefono,
            rol=request.rol,
            activo=request.activo,
            fecha_creacion=datetime.now(UTC)
        )

        return await self.repository.create(user)

    async def update(
        self,
        user_id: UUID,
        request: UserUpdate
    ):
        user = await self.repository.get_by_id(user_id)

        if not user:
            raise ValueError("Usuario no encontrado")

        if (
            request.correo
            and request.correo != user.correo
        ):
            existing_user = (
                await self.repository.get_by_email(
                    request.correo
                )
            )

            if existing_user:
                raise ValueError(
                    "El correo ya se encuentra registrado"
                )

        update_data = request.model_dump(
            exclude_unset=True
        )

        if "contrasena" in update_data:
            update_data["contrasena"] = hash_password(
                update_data["contrasena"]
            )

        for field, value in update_data.items():
            setattr(user, field, value)

        return await self.repository.update(user)

    async def delete(
        self,
        user_id: UUID
    ):
        user = await self.repository.get_by_id(
            user_id
        )

        if not user:
            raise ValueError(
                "Usuario no encontrado"
            )

        await self.repository.delete(user)