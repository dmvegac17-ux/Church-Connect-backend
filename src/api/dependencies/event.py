from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.events.services import EventService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.event_repository import EventRepository
from src.infrastructure.repositories.schedule_repository import ScheduleRepository


def get_event_service(
    db: AsyncSession = Depends(get_db)
) -> EventService:

    repository = EventRepository(db)
    schedule_repository = ScheduleRepository(db)

    return EventService(repository, schedule_repository)