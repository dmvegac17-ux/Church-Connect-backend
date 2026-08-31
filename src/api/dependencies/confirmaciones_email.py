from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.confirmaciones_email.services import ConfirmacionEmailService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.confirmacion_email_repository import ConfirmacionEmailRepository
from src.infrastructure.repositories.event_repository import EventRepository


def get_confirmacion_email_service(
    db: AsyncSession = Depends(get_db)
) -> ConfirmacionEmailService:

    repository = ConfirmacionEmailRepository(db)
    event_repository = EventRepository(db)

    return ConfirmacionEmailService(
        repository,
        event_repository
    )
