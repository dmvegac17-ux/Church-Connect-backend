from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.schedules.services import ScheduleService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.event_repository import EventRepository
from src.infrastructure.repositories.schedule_repository import ScheduleRepository


def get_schedule_service(
    db: AsyncSession = Depends(get_db)
) -> ScheduleService:

    repository = ScheduleRepository(db)
    event_repository = EventRepository(db)

    return ScheduleService(
        repository,
        event_repository
    )
