from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.registrations.services import RegistrationService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.event_repository import EventRepository
from src.infrastructure.repositories.registration_repository import RegistrationRepository


def get_registration_service(
    db: AsyncSession = Depends(get_db)
) -> RegistrationService:

    repository = RegistrationRepository(db)
    event_repository = EventRepository(db)

    return RegistrationService(
        repository,
        event_repository
    )
