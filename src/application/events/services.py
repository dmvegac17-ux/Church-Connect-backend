from uuid import UUID
from uuid import uuid4

from src.api.v1.events.schemas import EventCreate
from src.api.v1.events.schemas import EventUpdate
from src.infrastructure.database.models.event_model import EventModel
from src.infrastructure.repositories.event_repository import EventRepository


class EventService:

    def __init__(
        self,
        repository: EventRepository
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
        event_id: UUID
    ):
        event = await self.repository.get_by_id(
            event_id
        )

        if not event:
            raise ValueError(
                "Evento no encontrado"
            )

        return event

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
            capacidad=request.capacidad,
            creado_por=str(user_id)
        )

        return await self.repository.create(
            event
        )

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

        return await self.repository.update(
            event
        )

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