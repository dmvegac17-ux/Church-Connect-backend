from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class ScheduleCreate(BaseModel):
    evento_id: UUID
    actividad: str
    hora_inicio: datetime
    hora_fin: datetime
    responsable: str


class ScheduleUpdate(BaseModel):
    actividad: str | None = None
    hora_inicio: datetime | None = None
    hora_fin: datetime | None = None
    responsable: str | None = None


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
