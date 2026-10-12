from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.event_model import EventModel
from src.infrastructure.database.models.registration_model import RegistrationModel
from src.infrastructure.database.models.user_model import UserModel


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

    async def get_by_id_for_update(
        self,
        event_id: UUID
    ):
        query = (
            select(EventModel)
            .where(EventModel.id == event_id)
            .with_for_update()
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def rollback(self) -> None:
        await self.db.rollback()

    async def registered_users(
        self,
        event_id: UUID
    ) -> list[UserModel]:
        """Personas inscritas como público en el evento."""
        result = await self.db.execute(
            select(UserModel)
            .join(RegistrationModel, RegistrationModel.usuario_id == UserModel.id)
            .where(RegistrationModel.evento_id == event_id)
            .order_by(UserModel.nombre.asc())
        )

        return list(result.scalars().all())

    def add_all(self, entities: list) -> None:
        """Suma entidades a la transacción en curso (sin confirmar)."""
        self.db.add_all(entities)

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