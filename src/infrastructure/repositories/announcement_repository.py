from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.announcement_model import AnnouncementModel


class AnnouncementRepository:

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
            select(AnnouncementModel)
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def count(self) -> int:
        query = select(func.count()).select_from(
            AnnouncementModel
        )

        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_by_id(
        self,
        announcement_id: UUID
    ):
        query = select(AnnouncementModel).where(
            AnnouncementModel.id == announcement_id
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def create(
        self,
        announcement: AnnouncementModel
    ):
        self.db.add(announcement)

        await self.db.commit()

        await self.db.refresh(announcement)

        return announcement

    async def delete(
        self,
        announcement: AnnouncementModel
    ) -> None:
        await self.db.delete(announcement)

        await self.db.commit()

    async def update(
        self,
        announcement: AnnouncementModel
    ):
        await self.db.commit()

        await self.db.refresh(announcement)

        return announcement