from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class ScheduleCreate(BaseModel):
    evento_id: UUID
    actividad: str = Field(min_length=1, max_length=150)
    hora_inicio: datetime
    hora_fin: datetime
    responsable: str = Field(min_length=1, max_length=150)
    descripcion: str | None = Field(default=None, max_length=1000)


class ScheduleUpdate(BaseModel):
    actividad: str | None = Field(default=None, min_length=1, max_length=150)
    hora_inicio: datetime | None = None
    hora_fin: datetime | None = None
    responsable: str | None = Field(default=None, min_length=1, max_length=150)
    descripcion: str | None = Field(default=None, max_length=1000)


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    evento_id: UUID
    actividad: str
    hora_inicio: datetime
    hora_fin: datetime
    responsable: str
    descripcion: str | None = None
