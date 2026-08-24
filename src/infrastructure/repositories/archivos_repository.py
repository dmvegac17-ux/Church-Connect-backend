from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.archivos_model import ArchivosModel


class ArchivosRepository:

    def __init__(
        self,
        db: AsyncSession
    ):
        self.db = db

    async def get_all(
        self,
        limit: int,
        offset: int
    ):
        query = (
            select(ArchivosModel)
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def count(self) -> int:
        query = select(func.count()).select_from(
            ArchivosModel
        )

        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_by_id(
        self,
        archivo_id: UUID
    ):
        query = select(ArchivosModel).where(
            ArchivosModel.id == archivo_id
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def create(
        self,
        archivo: ArchivosModel
    ):
        self.db.add(archivo)

        await self.db.commit()

        await self.db.refresh(archivo)

        return archivo

    async def delete(
        self,
        archivo: ArchivosModel
    ) -> None:
        await self.db.delete(archivo)

        await self.db.commit()

    async def update(
        self,
        archivo: ArchivosModel
    ):
        await self.db.commit()

        await self.db.refresh(archivo)

        return archivo