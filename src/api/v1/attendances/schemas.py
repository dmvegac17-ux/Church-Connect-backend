from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class AttendanceCreate(BaseModel):
    usuario_id: UUID
    evento_id: UUID
    asistio: bool


class AttendanceUpdate(BaseModel):
    usuario_id: UUID | None = None
    evento_id: UUID | None = None
    asistio: bool | None = None


class AttendanceResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    usuario_id: UUID | None
    evento_id: UUID | None
    asistio: bool | None
    fecha_registro: datetime | None
    publicado_por: str
