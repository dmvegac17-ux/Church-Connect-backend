from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.attendances.services import AttendanceService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.attendance_repository import AttendanceRepository
from src.infrastructure.repositories.event_repository import EventRepository
from src.infrastructure.repositories.user_repository import UserRepository


def get_attendance_service(
    db: AsyncSession = Depends(get_db)
) -> AttendanceService:

    repository = AttendanceRepository(db)
    user_repository = UserRepository(db)
    event_repository = EventRepository(db)

    return AttendanceService(
        repository,
        user_repository,
        event_repository
    )
