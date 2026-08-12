from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.events.services import EventService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.event_repository import EventRepository


def get_event_service(
    db: AsyncSession = Depends(get_db)
) -> EventService:

    repository = EventRepository(db)

    return EventService(repository)