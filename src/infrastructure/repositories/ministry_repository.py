from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.ministry_model import MinistryModel


class MinistryRepository:

    def __init__(
        self,
        db: AsyncSession
    ):
        self.db = db

    async def get_all(
        self,
        limit: int,
        offset: int
    ):
        query = (
            select(MinistryModel)
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def count(self) -> int:
        query = select(func.count()).select_from(
            MinistryModel
        )

        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_by_id(
        self,
        ministry_id: UUID
    ):
        query = select(MinistryModel).where(
            MinistryModel.id == ministry_id
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def create(
        self,
        ministry: MinistryModel
    ):
        self.db.add(ministry)

        await self.db.commit()

        await self.db.refresh(ministry)

        return ministry

    async def delete(
        self,
        ministry: MinistryModel
    ) -> None:
        await self.db.delete(ministry)

        await self.db.commit()

    async def update(
        self,
        ministry: MinistryModel
    ):
        await self.db.commit()

        await self.db.refresh(ministry)

        return ministry
