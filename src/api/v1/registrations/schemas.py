from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class RegistrationCreate(BaseModel):
    evento_id: UUID


class RegistrationResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    usuario_id: UUID
    evento_id: UUID
    fecha_inscripcion: datetime
