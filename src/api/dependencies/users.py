from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.users.services import UserService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.user_repository import UserRepository


def get_user_service(
    db: AsyncSession = Depends(get_db)
) -> UserService:

    repository = UserRepository(db)

    return UserService(repository)