from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.user_ministry_model import UserMinistryModel
from src.infrastructure.database.models.user_model import UserModel


class UserMinistryRepository:

    def __init__(
        self,
        db: AsyncSession
    ):
        self.db = db

    async def get_members(
        self,
        ministry_id: UUID,
        limit: int,
        offset: int
    ):
        query = (
            select(UserModel)
            .join(
                UserMinistryModel,
                UserMinistryModel.usuario_id == UserModel.id
            )
            .where(UserMinistryModel.ministerio_id == ministry_id)
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def count_members(
        self,
        ministry_id: UUID
    ) -> int:
        query = (
            select(func.count())
            .select_from(UserMinistryModel)
            .where(UserMinistryModel.ministerio_id == ministry_id)
        )

        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_membership(
        self,
        ministry_id: UUID,
        user_id: UUID
    ):
        query = select(UserMinistryModel).where(
            UserMinistryModel.ministerio_id == ministry_id,
            UserMinistryModel.usuario_id == user_id
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def create(
        self,
        membership: UserMinistryModel
    ):
        self.db.add(membership)

        await self.db.commit()

        await self.db.refresh(membership)

        return membership

    async def delete(
        self,
        membership: UserMinistryModel
    ) -> None:
        await self.db.delete(membership)

        await self.db.commit()
