from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class NotificationCreate(BaseModel):
    titulo: str
    mensaje: str
    usuario_id: UUID


class NotificationUpdate(BaseModel):
    titulo: str | None = None
    mensaje: str | None = None
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