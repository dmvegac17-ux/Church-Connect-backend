from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.infrastructure.database.models.announcement_model import AnnouncementModel
from src.infrastructure.database.models.perfil_model import PerfilModel

Autor = aliased(PerfilModel, name="autor")
Editor = aliased(PerfilModel, name="editor")


class AnnouncementRepository:

    def __init__(
        self,
        db: AsyncSession
    ):
        self.db = db

    @staticmethod
    def _con_nombres():
        """
        El anuncio con el nombre de quien publicó y de quien actualizó, en
        una sola consulta (sin una consulta extra por fila).
        """
        return (
            select(
                AnnouncementModel,
                Autor.nombre,
                Autor.apellido,
                Editor.nombre,
                Editor.apellido
            )
            .outerjoin(Autor, Autor.usuario_id == AnnouncementModel.publicado_por)
            .outerjoin(Editor, Editor.usuario_id == AnnouncementModel.actualizado_por)
            .execution_options(populate_existing=True)
        )

    async def get_all(
        self,
        limit: int,
        offset: int
    ):
        query = (
            self._con_nombres()
            .order_by(
                AnnouncementModel.fecha_publicacion.desc(),
                AnnouncementModel.id.desc()
            )
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.all()

    async def count(self) -> int:
        query = select(func.count()).select_from(
            AnnouncementModel
        )

        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_by_id(
        self,
        announcement_id: UUID
    ):
        query = select(AnnouncementModel).where(
            AnnouncementModel.id == announcement_id
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_detalle(
        self,
        announcement_id: UUID
    ):
        result = await self.db.execute(
            self._con_nombres().where(AnnouncementModel.id == announcement_id)
        )

        return result.first()

    async def create(
        self,
        announcement: AnnouncementModel
    ):
        self.db.add(announcement)

        await self.db.commit()

        return announcement

    async def delete(
        self,
        announcement: AnnouncementModel
    ) -> None:
        await self.db.delete(announcement)

        await self.db.commit()

    async def update(
        self,
        announcement: AnnouncementModel
    ):
        await self.db.commit()

        return announcement

    async def rollback(self) -> None:
        await self.db.rollback()
