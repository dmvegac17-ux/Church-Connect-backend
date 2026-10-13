from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.registration_model import RegistrationModel
from src.infrastructure.database.models.user_model import UserModel


class RegistrationRepository:

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
            select(RegistrationModel)
            .order_by(RegistrationModel.fecha_inscripcion.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def count(self) -> int:
        query = select(func.count()).select_from(
            RegistrationModel
        )

        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_by_event_id(
        self,
        evento_id: UUID,
        limit: int,
        offset: int
    ):
        query = (
            select(RegistrationModel)
            .where(RegistrationModel.evento_id == evento_id)
            .order_by(RegistrationModel.fecha_inscripcion.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def count_by_event_id(
        self,
        evento_id: UUID
    ) -> int:
        query = (
            select(func.count())
            .select_from(RegistrationModel)
            .where(RegistrationModel.evento_id == evento_id)
        )

        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_by_user_id(
        self,
        usuario_id: UUID,
        limit: int,
        offset: int
    ):
        query = (
            select(RegistrationModel)
            .where(RegistrationModel.usuario_id == usuario_id)
            .order_by(RegistrationModel.fecha_inscripcion.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def count_by_user_id(
        self,
        usuario_id: UUID
    ) -> int:
        query = (
            select(func.count())
            .select_from(RegistrationModel)
            .where(RegistrationModel.usuario_id == usuario_id)
        )

        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_by_id(
        self,
        registration_id: UUID
    ):
        query = select(RegistrationModel).where(
            RegistrationModel.id == registration_id
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_by_user_and_event(
        self,
        usuario_id: UUID,
        evento_id: UUID
    ):
        query = select(RegistrationModel).where(
            RegistrationModel.usuario_id == usuario_id,
            RegistrationModel.evento_id == evento_id
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def usuarios_por_id(
        self,
        usuario_ids: list[UUID]
    ) -> dict[UUID, UserModel]:
        if not usuario_ids:
            return {}

        result = await self.db.execute(
            select(UserModel).where(UserModel.id.in_(usuario_ids))
        )

        return {usuario.id: usuario for usuario in result.scalars().all()}

    async def rollback(self) -> None:
        await self.db.rollback()

    async def update(
        self,
        registration: RegistrationModel
    ):
        await self.db.commit()

        await self.db.refresh(registration)

        return registration

    async def create(
        self,
        registration: RegistrationModel
    ):
        self.db.add(registration)

        try:
            await self.db.commit()

        except IntegrityError:
            await self.db.rollback()
            raise

        await self.db.refresh(registration)

        return registration

    async def delete(
        self,
        registration: RegistrationModel
    ) -> None:
        await self.db.delete(registration)

        await self.db.commit()
