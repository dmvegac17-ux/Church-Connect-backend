from datetime import UTC
from datetime import datetime
from uuid import UUID
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from src.core.constants.enums import UserRole
from src.infrastructure.database.models.registration_model import RegistrationModel
from src.infrastructure.database.models.user_model import UserModel
from src.infrastructure.repositories.event_repository import EventRepository
from src.infrastructure.repositories.registration_repository import RegistrationRepository


class RegistrationNotFoundError(Exception):
    pass


class EventNotFoundError(Exception):
    pass


class EventFullError(Exception):
    pass


class DuplicateRegistrationError(Exception):
    pass


class ForbiddenRegistrationAccessError(Exception):
    pass


class RegistrationService:

    def __init__(
        self,
        repository: RegistrationRepository,
        event_repository: EventRepository
    ):
        self.repository = repository
        self.event_repository = event_repository

    async def get_all(
        self,
        limit: int,
        offset: int,
        evento_id: UUID | None = None
    ):
        if evento_id is not None:
            return await self.repository.get_by_event_id(
                evento_id=evento_id,
                limit=limit,
                offset=offset
            )

        return await self.repository.get_all(
            limit=limit,
            offset=offset
        )

    async def count(
        self,
        evento_id: UUID | None = None
    ) -> int:
        if evento_id is not None:
            return await self.repository.count_by_event_id(
                evento_id
            )

        return await self.repository.count()

    async def get_my_registrations(
        self,
        user_id: UUID,
        limit: int,
        offset: int
    ):
        return await self.repository.get_by_user_id(
            usuario_id=user_id,
            limit=limit,
            offset=offset
        )

    async def count_my_registrations(
        self,
        user_id: UUID
    ) -> int:
        return await self.repository.count_by_user_id(
            user_id
        )

    async def get_by_id(
        self,
        registration_id: UUID,
        current_user: UserModel
    ):
        registration = await self.repository.get_by_id(
            registration_id
        )

        if not registration:
            raise RegistrationNotFoundError(
                "Inscripción no encontrada"
            )

        self._ensure_owner_or_admin(
            registration,
            current_user
        )

        return registration

    async def create(
        self,
        evento_id: UUID,
        user_id: UUID
    ):
        # Bloquea la fila del evento hasta el commit: cualquier otra
        # inscripción concurrente al mismo evento espera aquí, cerrando la
        # condición de carrera tanto para el cupo como para el duplicado.
        event = await self.event_repository.get_by_id_for_update(
            evento_id
        )

        if not event:
            raise EventNotFoundError(
                "Evento no encontrado"
            )

        existing = await self.repository.get_by_user_and_event(
            usuario_id=user_id,
            evento_id=evento_id
        )

        if existing:
            raise DuplicateRegistrationError(
                "El usuario ya está inscrito en este evento"
            )

        current_count = await self.repository.count_by_event_id(
            evento_id
        )

        if current_count >= event.capacidad:
            raise EventFullError(
                "El evento no tiene cupos disponibles"
            )

        registration = RegistrationModel(
            id=uuid4(),
            usuario_id=user_id,
            evento_id=evento_id,
            fecha_inscripcion=datetime.now(UTC)
        )

        try:
            return await self.repository.create(
                registration
            )

        except IntegrityError:
            raise DuplicateRegistrationError(
                "El usuario ya está inscrito en este evento"
            )

    async def delete(
        self,
        registration_id: UUID,
        current_user: UserModel
    ):
        registration = await self.repository.get_by_id(
            registration_id
        )

        if not registration:
            raise RegistrationNotFoundError(
                "Inscripción no encontrada"
            )

        self._ensure_owner_or_admin(
            registration,
            current_user
        )

        await self.repository.delete(
            registration
        )

    def _ensure_owner_or_admin(
        self,
        registration: RegistrationModel,
        current_user: UserModel
    ) -> None:
        if (
            current_user.rol != UserRole.ADMIN
            and current_user.id != registration.usuario_id
        ):
            raise ForbiddenRegistrationAccessError(
                "No tiene permisos para acceder a esta inscripción"
            )
