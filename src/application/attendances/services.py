from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.api.v1.attendances.schemas import AttendanceCreate, AttendanceUpdate
from src.infrastructure.database.models.attendance_model import AttendanceModel
from src.infrastructure.database.models.event_model import EventModel
from src.infrastructure.database.models.user_model import UserModel
from src.infrastructure.repositories.attendance_repository import AttendanceRepository
from src.infrastructure.repositories.event_repository import EventRepository
from src.infrastructure.repositories.user_repository import UserRepository


class AttendanceNotFoundError(Exception):
    pass


class AttendanceUserNotFoundError(Exception):
    pass


class EventNotFoundError(Exception):
    pass


class DuplicateAttendanceError(Exception):
    pass


class AttendanceOutsideEventWindowError(Exception):
    pass


class AttendanceService:

    def __init__(
        self,
        repository: AttendanceRepository,
        user_repository: UserRepository,
        event_repository: EventRepository
    ):
        self.repository = repository
        self.user_repository = user_repository
        self.event_repository = event_repository

    async def get_all(
        self,
        limit: int,
        offset: int,
        usuario_id: UUID | None = None,
        evento_id: UUID | None = None
    ):
        return await self.repository.get_all(
            limit=limit,
            offset=offset,
            usuario_id=usuario_id,
            evento_id=evento_id
        )

    async def count(
        self,
        usuario_id: UUID | None = None,
        evento_id: UUID | None = None
    ) -> int:
        return await self.repository.count(
            usuario_id=usuario_id,
            evento_id=evento_id
        )

    async def get_by_id(
        self,
        attendance_id: UUID
    ):
        attendance = await self.repository.get_by_id(
            attendance_id
        )

        if not attendance:
            raise AttendanceNotFoundError(
                "Asistencia no encontrada"
            )

        return attendance

    async def create(
        self,
        request: AttendanceCreate,
        current_user: UserModel
    ):
        await self._ensure_user_exists(
            request.usuario_id
        )

        event = await self._get_event(
            request.evento_id
        )
        self._ensure_event_is_in_progress(event)

        await self._ensure_not_duplicate(
            usuario_id=request.usuario_id,
            evento_id=request.evento_id
        )

        attendance = AttendanceModel(
            id=uuid4(),
            usuario_id=request.usuario_id,
            evento_id=request.evento_id,
            asistio=request.asistio,
            fecha_registro=datetime.now(UTC),
            publicado_por=str(current_user.id)
        )

        return await self.repository.create(
            attendance
        )

    async def update(
        self,
        attendance_id: UUID,
        request: AttendanceUpdate
    ):
        attendance = await self.repository.get_by_id(
            attendance_id
        )

        if not attendance:
            raise AttendanceNotFoundError(
                "Asistencia no encontrada"
            )

        update_data = request.model_dump(
            exclude_unset=True
        )

        next_usuario_id = update_data.get(
            "usuario_id", attendance.usuario_id
        )

        next_evento_id = update_data.get(
            "evento_id", attendance.evento_id
        )

        if next_evento_id is None:
            raise EventNotFoundError(
                "Evento no encontrado"
            )

        if "usuario_id" in update_data:
            await self._ensure_user_exists(
                next_usuario_id
            )

        event = await self._get_event(next_evento_id)
        self._ensure_event_is_in_progress(event)

        if (
            next_usuario_id != attendance.usuario_id
            or next_evento_id != attendance.evento_id
        ):
            await self._ensure_not_duplicate(
                usuario_id=next_usuario_id,
                evento_id=next_evento_id,
                exclude_id=attendance.id
            )

        for field, value in update_data.items():
            setattr(
                attendance,
                field,
                value
            )

        return await self.repository.update(
            attendance
        )

    async def delete(
        self,
        attendance_id: UUID
    ):
        attendance = await self.repository.get_by_id(
            attendance_id
        )

        if not attendance:
            raise AttendanceNotFoundError(
                "Asistencia no encontrada"
            )

        await self.repository.delete(
            attendance
        )

    async def _ensure_user_exists(
        self,
        usuario_id: UUID
    ) -> None:
        user = await self.user_repository.get_by_id(
            usuario_id
        )

        if not user:
            raise AttendanceUserNotFoundError(
                "Usuario no encontrado"
            )

    async def _get_event(self, evento_id: UUID) -> EventModel:
        event = await self.event_repository.get_by_id(evento_id)

        if not event:
            raise EventNotFoundError(
                "Evento no encontrado"
            )
        return event

    @staticmethod
    def _ensure_event_is_in_progress(event: EventModel) -> None:
        now = datetime.now(UTC)
        start = event.fecha_inicio
        end = event.fecha_fin

        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)

        if not start <= now <= end:
            raise AttendanceOutsideEventWindowError(
                "La asistencia solo se puede confirmar durante el horario del evento"
            )

    async def _ensure_not_duplicate(
        self,
        usuario_id: UUID | None,
        evento_id: UUID | None,
        exclude_id: UUID | None = None
    ) -> None:
        if usuario_id is None or evento_id is None:
            return

        existing = await self.repository.get_by_user_and_event(
            usuario_id=usuario_id,
            evento_id=evento_id
        )

        if existing and existing.id != exclude_id:
            raise DuplicateAttendanceError(
                "Ya existe una asistencia registrada para este "
                "usuario en este evento"
            )
