from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.schedule_model import ScheduleModel


class ScheduleRepository:

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
            select(ScheduleModel)
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def get_by_id(
        self,
        schedule_id: UUID
    ):
        query = select(ScheduleModel).where(
            ScheduleModel.id == schedule_id
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_by_evento_id(
        self,
        evento_id: UUID
    ):
        query = select(ScheduleModel).where(
            ScheduleModel.evento_id == evento_id
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def create(
        self,
        schedule: ScheduleModel
    ):
        self.db.add(schedule)

        await self.db.commit()

        await self.db.refresh(schedule)

        return schedule

    async def update(
        self,
        schedule: ScheduleModel
    ):
        await self.db.commit()

        await self.db.refresh(schedule)

        return schedule

    async def delete(
        self,
        schedule: ScheduleModel
    ):
        await self.db.delete(schedule)

        await self.db.commit()