from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.core.constants.enums import EstadoConfirmacion
from src.infrastructure.database.base import Base


class ConfirmacionEmailModel(Base):
    __tablename__ = "confirmaciones_email"

    id: Mapped[UUID] = mapped_column(
        primary_key=True
    )

    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )

    evento_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"),
        nullable=False
    )

    telefono: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    mensaje: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    estado: Mapped[EstadoConfirmacion] = mapped_column(
        SQLAlchemyEnum(
            EstadoConfirmacion,
            name="estado_confirmacion",
            native_enum=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            length=30
        ),
        nullable=False
    )

    fecha_envio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
