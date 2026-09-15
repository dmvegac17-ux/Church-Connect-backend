from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class AnnouncementCreate(BaseModel):
    titulo: str
    contenido: str
    imagen_url: str | None = None


class AnnouncementUpdate(BaseModel):
    titulo: str | None = None
    contenido: str | None = None
    imagen_url: str | None = None


class AnnouncementResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    titulo: str
    contenido: str
    imagen_url: str | None
    publicado_por: UUID
    fecha_publicacion: datetime


class AnnouncementListResponse(BaseModel):
    total: int
    items: list[AnnouncementResponse]