from uuid import UUID
from uuid import uuid4

from src.api.v1.schedules.schemas import ScheduleCreate
from src.api.v1.schedules.schemas import ScheduleUpdate
from src.infrastructure.database.models.schedule_model import ScheduleModel
from src.infrastructure.repositories.event_repository import EventRepository
from src.infrastructure.repositories.schedule_repository import ScheduleRepository


class ScheduleNotFoundError(Exception):
    pass


class EventNotFoundError(Exception):
    pass


class InvalidScheduleTimeError(Exception):
    pass


class ScheduleOutOfEventRangeError(Exception):
    pass


class ScheduleOverlapError(Exception):
    pass


class ScheduleService:

    def __init__(
        self,
        repository: ScheduleRepository,
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
            return await self.repository.get_by_evento_id(
                evento_id
            )

        return await self.repository.get_all(
            limit=limit,
            offset=offset
        )

    async def count(
        self,
        evento_id: UUID | None = None
    ) -> int:
        return await self.repository.count(
            evento_id
        )

    async def get_by_id(
        self,
        schedule_id: UUID
    ):
        schedule = await self.repository.get_by_id(
            schedule_id
        )

        if not schedule:
            raise ScheduleNotFoundError(
                "Cronograma no encontrado"
            )

        return schedule

    async def create(
        self,
        request: ScheduleCreate
    ):
        event = await self.event_repository.get_by_id(
            request.evento_id
        )

        if not event:
            raise EventNotFoundError(
                "Evento no encontrado"
            )

        if request.hora_fin <= request.hora_inicio:
            raise InvalidScheduleTimeError(
                "hora_fin debe ser posterior a hora_inicio"
            )

        existing = await self.repository.get_by_evento_id(
            event.id
        )

        self._validate_range_and_overlap(
            event=event,
            hora_inicio=request.hora_inicio,
            hora_fin=request.hora_fin,
            existing_schedules=existing,
            schedule_id=None
        )

        schedule = ScheduleModel(
            id=uuid4(),
            evento_id=request.evento_id,
            actividad=request.actividad,
            hora_inicio=request.hora_inicio,
            hora_fin=request.hora_fin,
            responsable=request.responsable,
            descripcion=request.descripcion
        )

        return await self.repository.create(
            schedule
        )

    async def update(
        self,
        schedule_id: UUID,
        request: ScheduleUpdate
    ):
        schedule = await self.get_by_id(
            schedule_id
        )

        update_data = request.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(schedule, field, value)

        if schedule.hora_fin <= schedule.hora_inicio:
            raise InvalidScheduleTimeError(
                "hora_fin debe ser posterior a hora_inicio"
            )

        event = await self.event_repository.get_by_id(
            schedule.evento_id
        )

        if not event:
            raise EventNotFoundError(
                "Evento no encontrado"
            )

        existing = await self.repository.get_by_evento_id(
            event.id
        )

        self._validate_range_and_overlap(
            event=event,
            hora_inicio=schedule.hora_inicio,
            hora_fin=schedule.hora_fin,
            existing_schedules=existing,
            schedule_id=schedule.id
        )

        return await self.repository.update(
            schedule
        )

    def _validate_range_and_overlap(
        self,
        event,
        hora_inicio,
        hora_fin,
        existing_schedules,
        schedule_id: UUID | None
    ) -> None:
        if hora_inicio < event.fecha_inicio or hora_fin > event.fecha_fin:
            raise ScheduleOutOfEventRangeError(
                "El cronograma debe estar dentro del rango de fechas "
                "del evento"
            )

        for other in existing_schedules:
            if schedule_id is not None and other.id == schedule_id:
                continue

            if other.hora_inicio < hora_fin and other.hora_fin > hora_inicio:
                raise ScheduleOverlapError(
                    "El horario se solapa con otra actividad del "
                    "cronograma de este evento"
                )

    async def delete(
        self,
        schedule_id: UUID
    ):
        schedule = await self.get_by_id(
            schedule_id
        )

        await self.repository.delete(
            schedule
        )
