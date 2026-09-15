from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class EventCreate(BaseModel):
    titulo: str
    descripcion: str
    fecha_inicio: datetime
    fecha_fin: datetime
    lugar: str
    capacidad: int


class EventUpdate(BaseModel):
    titulo: str | None = None
    descripcion: str | None = None
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    lugar: str | None = None
    capacidad: int | None = None


class EventResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    titulo: str
    descripcion: str
    fecha_inicio: datetime
    fecha_fin: datetime
    lugar: str
    capacidad: int
    creado_por: str