from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict

from src.core.constants.enums import EstadoConfirmacion


class ConfirmacionEmailCreate(BaseModel):
    evento_id: UUID
    telefono: str | None = None
    mensaje: str | None = None
    estado: EstadoConfirmacion


class ConfirmacionEmailUpdate(BaseModel):
    telefono: str | None = None
    mensaje: str | None = None
    estado: EstadoConfirmacion | None = None


class ConfirmacionEmailResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    usuario_id: UUID
    evento_id: UUID
    telefono: str | None
    mensaje: str | None
    estado: EstadoConfirmacion
    fecha_envio: datetime
