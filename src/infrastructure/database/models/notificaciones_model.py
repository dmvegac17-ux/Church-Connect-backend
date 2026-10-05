from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class NotificacionesModel(Base):
    __tablename__ = "notificaciones"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4
    )

    usuario_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=True
    )

    titulo: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    mensaje: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    leida: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True
    )

    fecha_envio: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )