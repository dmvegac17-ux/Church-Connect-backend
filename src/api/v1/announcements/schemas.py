from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AnnouncementPerson(BaseModel):
    id: UUID
    nombre_completo: str


class AnnouncementResponse(BaseModel):
    id: UUID
    titulo: str
    contenido: str
    imagen_url: str | None = None
    # Nulo si la cuenta de quien publicó o editó ya no existe.
    publicado_por: AnnouncementPerson | None = None
    fecha_publicacion: datetime
    actualizado_por: AnnouncementPerson | None = None
    # Nulo si nunca se editó.
    fecha_actualizacion: datetime | None = None
