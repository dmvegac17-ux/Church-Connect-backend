from uuid import UUID
from uuid import uuid4

from src.api.v1.events.schemas import EventCreate
from src.api.v1.events.schemas import EventUpdate
from src.infrastructure.database.models.event_model import EventModel
from src.infrastructure.repositories.event_repository import EventRepository
from src.infrastructure.repositories.schedule_repository import ScheduleRepository


class InvalidEventDateRangeError(Exception):
    pass


class InvalidEventLocationError(Exception):
    pass


class EventService:

    def __init__(
        self,
        repository: EventRepository,
        schedule_repository: ScheduleRepository
    ):
        self.repository = repository
        self.schedule_repository = schedule_repository

    async def _attach_schedule_counts(
        self,
        events: list[EventModel]
    ) -> list[EventModel]:
        counts = await self.schedule_repository.count_by_evento_ids(
            [event.id for event in events]
        )

        for event in events:
            event.total_actividades = counts.get(event.id, 0)

        return events

    async def get_all(
        self,
        limit: int,
        offset: int
    ):
        events = await self.repository.get_all(
            limit=limit,
            offset=offset
        )

        return await self._attach_schedule_counts(
            list(events)
        )

    async def count(self) -> int:
        return await self.repository.count()

    async def get_by_id(
        self,
        event_id: UUID
    ):
        event = await self.repository.get_by_id(
            event_id
        )

        if not event:
            raise ValueError(
                "Evento no encontrado"
            )

        await self._attach_schedule_counts([event])

        return event

    def _validate(
        self,
        event: EventModel
    ) -> None:
        if event.fecha_fin <= event.fecha_inicio:
            raise InvalidEventDateRangeError(
                "La fecha/hora de fin debe ser posterior a la "
                "fecha/hora de inicio"
            )

        has_lat = event.latitud is not None
        has_lng = event.longitud is not None
        if has_lat != has_lng:
            raise InvalidEventLocationError(
                "latitud y longitud deben enviarse juntas o no enviarse"
            )

    async def create(
        self,
        request: EventCreate,
        user_id: UUID
    ):
        event = EventModel(
            id=uuid4(),
            titulo=request.titulo,
            descripcion=request.descripcion,
            fecha_inicio=request.fecha_inicio,
            fecha_fin=request.fecha_fin,
            lugar=request.lugar,
            direccion=request.direccion,
            latitud=request.latitud,
            longitud=request.longitud,
            capacidad=request.capacidad,
            creado_por=str(user_id)
        )

        self._validate(event)

        created = await self.repository.create(
            event
        )

        created.total_actividades = 0

        return created

    async def update(
        self,
        event_id: UUID,
        request: EventUpdate
    ):
        event = await self.repository.get_by_id(
            event_id
        )

        if not event:
            raise ValueError(
                "Evento no encontrado"
            )

        update_data = request.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(event, field, value)

        self._validate(event)

        updated = await self.repository.update(
            event
        )

        await self._attach_schedule_counts([updated])

        return updated

    async def delete(
        self,
        event_id: UUID
    ):
        event = await self.repository.get_by_id(
            event_id
        )

        if not event:
            raise ValueError(
                "Evento no encontrado"
            )

        await self.repository.delete(
            event
        )