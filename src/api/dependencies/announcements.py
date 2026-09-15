from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.announcements.services import AnnouncementService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.announcement_repository import AnnouncementRepository


def get_announcement_service(
    db: AsyncSession = Depends(get_db)
) -> AnnouncementService:

    repository = AnnouncementRepository(db)

    return AnnouncementService(repository)