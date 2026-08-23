from datetime import UTC
from datetime import datetime
from uuid import UUID
from uuid import uuid4

from src.api.v1.notificaciones.schemas import NotificationCreate
from src.api.v1.notificaciones.schemas import NotificationUpdate
from src.infrastructure.database.models.notificaciones_model import NotificacionesModel
from src.infrastructure.repositories.notificaciones_repository import NotificacionesRepository


class NotificacionesService:

    def __init__(
        self,
        repository: NotificacionesRepository
    ):
        self.repository = repository

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
        notificacion_id: UUID
    ):
        notificacion = await self.repository.get_by_id(
            notificacion_id
        )

        if not notificacion:
            raise ValueError(
                "Notificación no encontrada"
            )

        return notificacion

    async def create(
        self,
        request: NotificationCreate,
        user_id: UUID
    ):
        notificacion = NotificacionesModel(
            id=uuid4(),
            usuario_id=user_id,
            titulo=request.titulo,
            mensaje=request.mensaje,
            leida=False,
            fecha_envio=datetime.now(UTC)
        )

        return await self.repository.create(
            notificacion
        )

    async def update(
        self,
        notificacion_id: UUID,
        request: NotificationUpdate
    ):
        notificacion = await self.repository.get_by_id(
            notificacion_id
        )

        if not notificacion:
            raise ValueError(
                "Notificación no encontrada"
            )

        update_data = request.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(
                notificacion,
                field,
                value
            )

        return await self.repository.update(
            notificacion
        )

    async def delete(
        self,
        notificacion_id: UUID
    ):
        notificacion = await self.repository.get_by_id(
            notificacion_id
        )

        if not notificacion:
            raise ValueError(
                "Notificación no encontrada"
            )

        await self.repository.delete(
            notificacion
        )