from datetime import UTC
from datetime import datetime
from uuid import UUID
from uuid import uuid4

from src.api.v1.confirmaciones_email.schemas import ConfirmacionEmailCreate
from src.api.v1.confirmaciones_email.schemas import ConfirmacionEmailUpdate
from src.core.constants.enums import EstadoConfirmacion
from src.core.constants.enums import UserRole
from src.infrastructure.database.models.confirmacion_email_model import ConfirmacionEmailModel
from src.infrastructure.database.models.user_model import UserModel
from src.infrastructure.repositories.confirmacion_email_repository import ConfirmacionEmailRepository
from src.infrastructure.repositories.event_repository import EventRepository


class ConfirmacionEmailNotFoundError(Exception):
    pass


class EventNotFoundError(Exception):
    pass


class ForbiddenConfirmacionAccessError(Exception):
    pass


class ConfirmacionEmailService:

    def __init__(
        self,
        repository: ConfirmacionEmailRepository,
        event_repository: EventRepository
    ):
        self.repository = repository
        self.event_repository = event_repository

    async def get_all(
        self,
        current_user: UserModel,
        limit: int,
        offset: int,
        usuario_id: UUID | None = None,
        evento_id: UUID | None = None,
        estado: EstadoConfirmacion | None = None
    ):
        if current_user.rol != UserRole.ADMIN:
            usuario_id = current_user.id

        return await self.repository.get_all(
            limit=limit,
            offset=offset,
            usuario_id=usuario_id,
            evento_id=evento_id,
            estado=estado
        )

    async def count(
        self,
        current_user: UserModel,
        usuario_id: UUID | None = None,
        evento_id: UUID | None = None,
        estado: EstadoConfirmacion | None = None
    ) -> int:
        if current_user.rol != UserRole.ADMIN:
            usuario_id = current_user.id

        return await self.repository.count(
            usuario_id=usuario_id,
            evento_id=evento_id,
            estado=estado
        )

    async def get_by_id(
        self,
        confirmacion_id: UUID,
        current_user: UserModel
    ):
        confirmacion = await self.repository.get_by_id(
            confirmacion_id
        )

        if not confirmacion:
            raise ConfirmacionEmailNotFoundError(
                "Confirmación no encontrada"
            )

        self._ensure_owner_or_admin(
            confirmacion,
            current_user
        )

        return confirmacion

    async def create(
        self,
        request: ConfirmacionEmailCreate,
        current_user: UserModel
    ):
        event = await self.event_repository.get_by_id(
            request.evento_id
        )

        if not event:
            raise EventNotFoundError(
                "Evento no encontrado"
            )

        confirmacion = ConfirmacionEmailModel(
            id=uuid4(),
            usuario_id=current_user.id,
            evento_id=request.evento_id,
            telefono=request.telefono,
            mensaje=request.mensaje,
            estado=request.estado,
            fecha_envio=datetime.now(UTC)
        )

        return await self.repository.create(
            confirmacion
        )

    async def update(
        self,
        confirmacion_id: UUID,
        request: ConfirmacionEmailUpdate,
        current_user: UserModel
    ):
        confirmacion = await self.repository.get_by_id(
            confirmacion_id
        )

        if not confirmacion:
            raise ConfirmacionEmailNotFoundError(
                "Confirmación no encontrada"
            )

        self._ensure_owner_or_admin(
            confirmacion,
            current_user
        )

        update_data = request.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(
                confirmacion,
                field,
                value
            )

        return await self.repository.update(
            confirmacion
        )

    async def delete(
        self,
        confirmacion_id: UUID,
        current_user: UserModel
    ):
        confirmacion = await self.repository.get_by_id(
            confirmacion_id
        )

        if not confirmacion:
            raise ConfirmacionEmailNotFoundError(
                "Confirmación no encontrada"
            )

        self._ensure_owner_or_admin(
            confirmacion,
            current_user
        )

        await self.repository.delete(
            confirmacion
        )

    def _ensure_owner_or_admin(
        self,
        confirmacion: ConfirmacionEmailModel,
        current_user: UserModel
    ) -> None:
        if (
            current_user.rol != UserRole.ADMIN
            and current_user.id != confirmacion.usuario_id
        ):
            raise ForbiddenConfirmacionAccessError(
                "No tiene permisos para acceder a esta confirmación"
            )
