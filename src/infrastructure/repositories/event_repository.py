from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.event_model import EventModel


class EventRepository:

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
            select(EventModel)
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def count(self) -> int:
        query = select(func.count()).select_from(
            EventModel
        )

        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_by_id(
        self,
        event_id: UUID
    ):
        query = select(EventModel).where(
            EventModel.id == event_id
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def create(
        self,
        event: EventModel
    ):
        self.db.add(event)

        await self.db.commit()

        await self.db.refresh(event)

        return event

    async def delete(
        self,
        event: EventModel
    ) -> None:
        await self.db.delete(event)

        await self.db.commit()

    async def update(
        self,
        event: EventModel
    ):
        await self.db.commit()

        await self.db.refresh(event)

        return event