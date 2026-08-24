from datetime import UTC
from datetime import datetime
from uuid import UUID
from uuid import uuid4

from src.api.v1.archivos.schemas import ArchivoCreate
from src.api.v1.archivos.schemas import ArchivoUpdate
from src.infrastructure.database.models.archivos_model import ArchivosModel
from src.infrastructure.repositories.archivos_repository import ArchivosRepository


class ArchivosService:

    def __init__(
        self,
        repository: ArchivosRepository
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
        archivo_id: UUID
    ):
        archivo = await self.repository.get_by_id(
            archivo_id
        )

        if not archivo:
            raise ValueError(
                "Archivo no encontrado"
            )

        return archivo

    async def create(
        self,
        request: ArchivoCreate,
        user_id: UUID
    ):
        archivo = ArchivosModel(
            id=uuid4(),
            nombre_archivo=request.nombre_archivo,
            url_archivo=request.url_archivo,
            tipo=request.tipo,
            subido_por=user_id,
            fecha_subida=datetime.now(UTC)
        )

        return await self.repository.create(
            archivo
        )

    async def update(
        self,
        archivo_id: UUID,
        request: ArchivoUpdate
    ):
        archivo = await self.repository.get_by_id(
            archivo_id
        )

        if not archivo:
            raise ValueError(
                "Archivo no encontrado"
            )

        update_data = request.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(
                archivo,
                field,
                value
            )

        return await self.repository.update(
            archivo
        )

    async def delete(
        self,
        archivo_id: UUID
    ):
        archivo = await self.repository.get_by_id(
            archivo_id
        )

        if not archivo:
            raise ValueError(
                "Archivo no encontrado"
            )

        await self.repository.delete(
            archivo
        )