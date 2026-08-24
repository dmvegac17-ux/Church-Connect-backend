from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class AttendanceModel(Base):
    __tablename__ = "asistencias"

    id: Mapped[UUID] = mapped_column(
        primary_key=True
    )

    usuario_id: Mapped[UUID | None] = mapped_column(
        nullable=True
    )

    evento_id: Mapped[UUID | None] = mapped_column(
        nullable=True
    )

    asistio: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True
    )

    fecha_registro: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    publicado_por: Mapped[str] = mapped_column(
        String,
        nullable=False
    )
