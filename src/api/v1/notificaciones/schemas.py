from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from src.core.schemas.fields import trimmed_text

NotificationTitle = trimmed_text(1, 200)
# El mensaje es HTML enriquecido: el tope de 2000 caracteres de texto lo aplica
# el redactor; aquí se limita el HTML para acotar el tamaño de la petición.
NotificationMessage = trimmed_text(1, 20000)


class NotificationCreate(BaseModel):
    titulo: NotificationTitle
    mensaje: NotificationMessage
    usuario_id: UUID


class NotificationBulkCreate(BaseModel):
    titulo: NotificationTitle
    mensaje: NotificationMessage
    usuarios_ids: list[UUID] = Field(default_factory=list)


class NotificationUpdate(BaseModel):
    titulo: NotificationTitle | None = None
    mensaje: NotificationMessage | None = None
    leida: bool | None = None


class NotificationResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    titulo: str
    mensaje: str
    usuario_id: UUID
    leida: bool
    fecha_envio: datetime


class NotificationListResponse(BaseModel):
    total: int
    items: list[NotificationResponse]