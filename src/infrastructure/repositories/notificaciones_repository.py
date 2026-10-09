from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.notificaciones_model import NotificacionesModel

class NotificacionesRepository:

    def __init__(
        self,
        db: AsyncSession
    ):
        self.db = db

    async def get_all(
        self,
        limit: int,
        offset: int,
        usuario_id: UUID | None = None
    ):
        query = select(NotificacionesModel)

        if usuario_id is not None:
            query = query.where(
                NotificacionesModel.usuario_id == usuario_id
            )

        query = (
            query
            .order_by(NotificacionesModel.fecha_envio.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def count(
        self,
        usuario_id: UUID | None = None
    ) -> int:
        query = select(func.count()).select_from(
            NotificacionesModel
        )

        if usuario_id is not None:
            query = query.where(
                NotificacionesModel.usuario_id == usuario_id
            )

        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_by_id(
        self,
        notificacion_id: UUID
    ):
        query = select(NotificacionesModel).where(
            NotificacionesModel.id == notificacion_id
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def create(
        self,
        notificacion: NotificacionesModel
    ):
        self.db.add(notificacion)

        await self.db.commit()

        await self.db.refresh(notificacion)

        return notificacion

    async def rollback(self) -> None:
        await self.db.rollback()

    async def delete(
        self,
        notificacion: NotificacionesModel
    ) -> None:
        await self.db.delete(notificacion)

        await self.db.commit()

    async def update(
        self,
        notificacion: NotificacionesModel
    ):
        await self.db.commit()

        await self.db.refresh(notificacion)

        return notificacion

