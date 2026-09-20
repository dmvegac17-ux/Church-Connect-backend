from datetime import UTC
from datetime import datetime
from uuid import UUID
from uuid import uuid4

from src.api.v1.notificaciones.schemas import NotificationBulkCreate
from src.api.v1.notificaciones.schemas import NotificationCreate
from src.api.v1.notificaciones.schemas import NotificationUpdate
from src.core.logging.logger import logger
from src.infrastructure.database.models.notificaciones_model import NotificacionesModel
from src.infrastructure.email.email_service import EmailService
from src.infrastructure.repositories.notificaciones_repository import NotificacionesRepository
from src.infrastructure.repositories.user_repository import UserRepository


class UserNotFoundError(Exception):
    pass


class NotificacionesService:

    def __init__(
        self,
        repository: NotificacionesRepository,
        user_repository: UserRepository,
        email_service: EmailService
    ):
        self.repository = repository
        self.user_repository = user_repository
        self.email_service = email_service

    async def get_all(
        self,
        limit: int,
        offset: int,
        usuario_id: UUID | None = None
    ):
        return await self.repository.get_all(
            limit=limit,
            offset=offset,
            usuario_id=usuario_id
        )

    async def count(
        self,
        usuario_id: UUID | None = None
    ) -> int:
        return await self.repository.count(
            usuario_id
        )

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
        request: NotificationCreate
    ):
        user = await self.user_repository.get_by_id(
            request.usuario_id
        )

        if not user:
            raise UserNotFoundError(
                "Usuario no encontrado"
            )

        notificacion = NotificacionesModel(
            id=uuid4(),
            usuario_id=request.usuario_id,
            titulo=request.titulo,
            mensaje=request.mensaje,
            leida=False,
            fecha_envio=datetime.now(UTC)
        )

        created = await self.repository.create(
            notificacion
        )

        await self.email_service.send(
            to=user.correo,
            subject=request.titulo,
            body=request.mensaje
        )

        return created

    async def create_bulk(
        self,
        request: NotificationBulkCreate
    ) -> tuple[list[NotificacionesModel], list[str]]:
        creadas: list[NotificacionesModel] = []
        errores: list[str] = []

        for usuario_id in request.usuarios_ids:
            try:
                user = await self.user_repository.get_by_id(
                    usuario_id
                )

                if not user:
                    errores.append(
                        f"{usuario_id}: Usuario no encontrado"
                    )
                    continue

                notificacion = NotificacionesModel(
                    id=uuid4(),
                    usuario_id=usuario_id,
                    titulo=request.titulo,
                    mensaje=request.mensaje,
                    leida=False,
                    fecha_envio=datetime.now(UTC)
                )

                created = await self.repository.create(
                    notificacion
                )

                creadas.append(created)

                await self.email_service.send(
                    to=user.correo,
                    subject=request.titulo,
                    body=request.mensaje
                )

            except Exception as ex:
                await self.repository.rollback()

                logger.exception(
                    "Fallo al crear la notificación masiva para %s",
                    usuario_id
                )

                errores.append(
                    f"{usuario_id}: {ex}"
                )

        return creadas, errores

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