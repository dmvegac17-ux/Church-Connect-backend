from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.announcements.services import AnnouncementService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.announcement_repository import AnnouncementRepository
from src.infrastructure.supabase.client import SupabaseStorage
from src.infrastructure.supabase.client import announcements_storage


def get_announcements_storage() -> SupabaseStorage:
    return announcements_storage


def get_announcement_service(
    db: AsyncSession = Depends(get_db),
    storage: SupabaseStorage = Depends(get_announcements_storage)
) -> AnnouncementService:

    repository = AnnouncementRepository(db)

    return AnnouncementService(repository, storage)
