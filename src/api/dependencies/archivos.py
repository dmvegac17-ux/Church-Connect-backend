from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.archivos.services import ArchivosService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.archivos_repository import ArchivosRepository


def get_archivos_service(
    db: AsyncSession = Depends(get_db)
) -> ArchivosService:

    repository = ArchivosRepository(db)

    return ArchivosService(repository)