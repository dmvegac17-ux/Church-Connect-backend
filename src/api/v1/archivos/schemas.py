from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class ArchivoCreate(BaseModel):
    nombre_archivo: str
    url_archivo: str
    tipo: str


class ArchivoUpdate(BaseModel):
    nombre_archivo: str | None = None
    url_archivo: str | None = None
    tipo: str | None = None


class ArchivoResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    nombre_archivo: str | None
    url_archivo: str | None
    tipo: str | None
    subido_por: UUID | None
    fecha_subida: datetime | None


class ArchivoListResponse(BaseModel):
    total: int
    items: list[ArchivoResponse]