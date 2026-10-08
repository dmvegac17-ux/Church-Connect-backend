from datetime import UTC
from datetime import datetime
from uuid import UUID
from uuid import uuid4

from src.api.v1.announcements.schemas import AnnouncementCreate
from src.api.v1.announcements.schemas import AnnouncementUpdate
from src.infrastructure.database.models.announcement_model import AnnouncementModel
from src.infrastructure.repositories.announcement_repository import AnnouncementRepository


class AnnouncementService:

    def __init__(
        self,
        repository: AnnouncementRepository
    ):
        self.repository = repository

    async def get_all(
        self,
        limit: int,
        offset: int
    ):
        return await self.repository.get_all(
            limit=limit,
            offset=offset
        )

    async def count(self) -> int:
        return await self.repository.count()

    async def get_by_id(
        self,
        announcement_id: UUID
    ):
        announcement = await self.repository.get_by_id(
            announcement_id
        )

        if not announcement:
            raise ValueError(
                "Anuncio no encontrado"
            )

        return announcement

    async def create(
        self,
        request: AnnouncementCreate,
        user_id: UUID
    ):
        announcement = AnnouncementModel(
            id=uuid4(),
            titulo=request.titulo,
            contenido=request.contenido,
            imagen_url=request.imagen_url,
            publicado_por=user_id,
            fecha_publicacion=datetime.now(UTC)
        )

        return await self.repository.create(
            announcement
        )

    async def update(
        self,
        announcement_id: UUID,
        request: AnnouncementUpdate
    ):
        announcement = await self.repository.get_by_id(
            announcement_id
        )

        if not announcement:
            raise ValueError(
                "Anuncio no encontrado"
            )

        update_data = request.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(
                announcement,
                field,
                value
            )

        return await self.repository.update(
            announcement
        )

    async def delete(
        self,
        announcement_id: UUID
    ):
        announcement = await self.repository.get_by_id(
            announcement_id
        )

        if not announcement:
            raise ValueError(
                "Anuncio no encontrado"
            )

        await self.repository.delete(
            announcement
        )