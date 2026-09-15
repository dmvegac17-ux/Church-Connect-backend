from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ministries.services import MinistryService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.ministry_repository import MinistryRepository
from src.infrastructure.repositories.user_ministry_repository import UserMinistryRepository
from src.infrastructure.repositories.user_repository import UserRepository


def get_ministry_service(
    db: AsyncSession = Depends(get_db)
) -> MinistryService:

    repository = MinistryRepository(db)
    member_repository = UserMinistryRepository(db)
    user_repository = UserRepository(db)

    return MinistryService(
        repository,
        member_repository,
        user_repository
    )
