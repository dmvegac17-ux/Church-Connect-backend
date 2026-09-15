from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class EventModel(Base):
    __tablename__ = "event"

    id: Mapped[UUID] = mapped_column(
        primary_key=True
    )

    titulo: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True
    )

    descripcion: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    fecha_inicio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    fecha_fin: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    lugar: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    capacidad: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    creado_por: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )