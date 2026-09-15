from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.notificaciones.services import NotificacionesService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.notificaciones_repository import NotificacionesRepository
from src.infrastructure.repositories.user_repository import UserRepository


def get_notificacion_service(
    db: AsyncSession = Depends(get_db)
) -> NotificacionesService:

    repository = NotificacionesRepository(db)
    user_repository = UserRepository(db)

    return NotificacionesService(
        repository,
        user_repository
    )