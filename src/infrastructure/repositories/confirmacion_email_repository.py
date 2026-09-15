from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants.enums import EstadoConfirmacion
from src.infrastructure.database.models.confirmacion_email_model import ConfirmacionEmailModel


class ConfirmacionEmailRepository:

    def __init__(
        self,
        db: AsyncSession
    ):
        self.db = db

    async def get_all(
        self,
        limit: int,
        offset: int,
        usuario_id: UUID | None = None,
        evento_id: UUID | None = None,
        estado: EstadoConfirmacion | None = None
    ):
        query = select(ConfirmacionEmailModel)

        if usuario_id is not None:
            query = query.where(
                ConfirmacionEmailModel.usuario_id == usuario_id
            )

        if evento_id is not None:
            query = query.where(
                ConfirmacionEmailModel.evento_id == evento_id
            )

        if estado is not None:
            query = query.where(
                ConfirmacionEmailModel.estado == estado
            )

        query = (
            query.order_by(ConfirmacionEmailModel.fecha_envio.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def count(
        self,
        usuario_id: UUID | None = None,
        evento_id: UUID | None = None,
        estado: EstadoConfirmacion | None = None
    ) -> int:
        query = select(func.count()).select_from(
            ConfirmacionEmailModel
        )

        if usuario_id is not None:
            query = query.where(
                ConfirmacionEmailModel.usuario_id == usuario_id
            )

        if evento_id is not None:
            query = query.where(
                ConfirmacionEmailModel.evento_id == evento_id
            )

        if estado is not None:
            query = query.where(
                ConfirmacionEmailModel.estado == estado
            )

        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_by_id(
        self,
        confirmacion_id: UUID
    ):
        query = select(ConfirmacionEmailModel).where(
            ConfirmacionEmailModel.id == confirmacion_id
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def create(
        self,
        confirmacion: ConfirmacionEmailModel
    ):
        self.db.add(confirmacion)

        await self.db.commit()

        await self.db.refresh(confirmacion)

        return confirmacion

    async def update(
        self,
        confirmacion: ConfirmacionEmailModel
    ):
        await self.db.commit()

        await self.db.refresh(confirmacion)

        return confirmacion

    async def delete(
        self,
        confirmacion: ConfirmacionEmailModel
    ) -> None:
        await self.db.delete(confirmacion)

        await self.db.commit()
