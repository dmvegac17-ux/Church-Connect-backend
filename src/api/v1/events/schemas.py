from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class EventCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=150)
    descripcion: str = Field(min_length=1, max_length=2000)
    fecha_inicio: datetime
    fecha_fin: datetime
    lugar: str = Field(min_length=1, max_length=200)
    direccion: str | None = Field(default=None, max_length=255)
    latitud: float | None = Field(default=None, ge=-90, le=90)
    longitud: float | None = Field(default=None, ge=-180, le=180)
    capacidad: int = Field(gt=0)


class EventUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=150)
    descripcion: str | None = Field(default=None, min_length=1, max_length=2000)
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    lugar: str | None = Field(default=None, min_length=1, max_length=200)
    direccion: str | None = Field(default=None, max_length=255)
    latitud: float | None = Field(default=None, ge=-90, le=90)
    longitud: float | None = Field(default=None, ge=-180, le=180)
    capacidad: int | None = Field(default=None, gt=0)


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
    direccion: str | None = None
    latitud: float | None = None
    longitud: float | None = None
    capacidad: int
    creado_por: str
    total_actividades: int = 0
