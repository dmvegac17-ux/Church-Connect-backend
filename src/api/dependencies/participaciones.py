from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.participaciones.services import ParticipacionService
from src.infrastructure.database.session import get_db
from src.infrastructure.email.email_service import EmailService
from src.infrastructure.email.email_service import email_service
from src.infrastructure.repositories.invitacion_participacion_repository import (
    InvitacionParticipacionRepository,
)


def get_email_service() -> EmailService:
    return email_service


def get_participacion_service(
    db: AsyncSession = Depends(get_db),
    mailer: EmailService = Depends(get_email_service)
) -> ParticipacionService:

    repository = InvitacionParticipacionRepository(db)

    return ParticipacionService(
        repository,
        mailer
    )
