from uuid import UUID
from uuid import uuid4

from src.api.v1.ministries.schemas import MinistryCreate
from src.api.v1.ministries.schemas import MinistryUpdate
from src.infrastructure.database.models.ministry_model import MinistryModel
from src.infrastructure.database.models.user_ministry_model import UserMinistryModel
from src.infrastructure.repositories.ministry_repository import MinistryRepository
from src.infrastructure.repositories.user_ministry_repository import UserMinistryRepository
from src.infrastructure.repositories.user_repository import UserRepository


class MinistryNotFoundError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class DuplicateMembershipError(Exception):
    pass


class MembershipNotFoundError(Exception):
    pass


class MinistryService:

    def __init__(
        self,
        repository: MinistryRepository,
        member_repository: UserMinistryRepository,
        user_repository: UserRepository
    ):
        self.repository = repository
        self.member_repository = member_repository
        self.user_repository = user_repository

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
        ministry_id: UUID
    ):
        ministry = await self.repository.get_by_id(
            ministry_id
        )

        if not ministry:
            raise MinistryNotFoundError(
                "Ministerio no encontrado"
            )

        return ministry

    async def create(
        self,
        request: MinistryCreate
    ):
        ministry = MinistryModel(
            id=uuid4(),
            nombre=request.nombre,
            descripcion=request.descripcion
        )

        return await self.repository.create(
            ministry
        )

    async def update(
        self,
        ministry_id: UUID,
        request: MinistryUpdate
    ):
        ministry = await self.get_by_id(
            ministry_id
        )

        update_data = request.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(ministry, field, value)

        return await self.repository.update(
            ministry
        )

    async def delete(
        self,
        ministry_id: UUID
    ):
        ministry = await self.get_by_id(
            ministry_id
        )

        await self.repository.delete(
            ministry
        )

    async def list_members(
        self,
        ministry_id: UUID,
        limit: int,
        offset: int
    ):
        await self.get_by_id(
            ministry_id
        )

        return await self.member_repository.get_members(
            ministry_id=ministry_id,
            limit=limit,
            offset=offset
        )

    async def count_members(
        self,
        ministry_id: UUID
    ) -> int:
        return await self.member_repository.count_members(
            ministry_id
        )

    async def add_member(
        self,
        ministry_id: UUID,
        user_id: UUID
    ):
        await self.get_by_id(
            ministry_id
        )

        user = await self.user_repository.get_by_id(
            user_id
        )

        if not user:
            raise UserNotFoundError(
                "Usuario no encontrado"
            )

        existing = await self.member_repository.get_membership(
            ministry_id=ministry_id,
            user_id=user_id
        )

        if existing:
            raise DuplicateMembershipError(
                "El usuario ya pertenece a este ministerio"
            )

        membership = UserMinistryModel(
            id=uuid4(),
            usuario_id=user_id,
            ministerio_id=ministry_id
        )

        await self.member_repository.create(
            membership
        )

    async def remove_member(
        self,
        ministry_id: UUID,
        user_id: UUID
    ):
        await self.get_by_id(
            ministry_id
        )

        membership = await self.member_repository.get_membership(
            ministry_id=ministry_id,
            user_id=user_id
        )

        if not membership:
            raise MembershipNotFoundError(
                "El usuario no pertenece a este ministerio"
            )

        await self.member_repository.delete(
            membership
        )
