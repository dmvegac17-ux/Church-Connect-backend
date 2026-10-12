from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class NotificacionesModel(Base):
    __tablename__ = "notificaciones"
    __table_args__ = (
        # La bandeja de cada persona, de la más reciente a la más antigua.
        Index("ix_notificaciones_usuario_fecha", "usuario_id", "fecha_envio"),
        # El contador de no leídas y «marcar todas»: solo indexa las pendientes.
        Index(
            "ix_notificaciones_no_leidas",
            "usuario_id",
            postgresql_where=text("leida = false"),
            sqlite_where=text("leida = 0")
        ),
    )

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