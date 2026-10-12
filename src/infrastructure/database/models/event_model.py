from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class EventModel(Base):
    __tablename__ = "event"
    __table_args__ = (
        CheckConstraint(
            "char_length(descripcion) <= 2000",
            name="ck_event_descripcion_length"
        ),
        CheckConstraint(
            "dias_limite_cancelacion IS NULL OR "
            "(dias_limite_cancelacion >= 0 AND dias_limite_cancelacion <= 365)",
            name="ck_event_dias_limite_cancelacion"
        ),
        CheckConstraint(
            "fecha_limite_inscripcion IS NULL OR "
            "fecha_limite_inscripcion <= fecha_inicio",
            name="ck_event_fecha_limite_inscripcion"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True
    )

    titulo: Mapped[str] = mapped_column(
        String(150),
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
        String(200),
        nullable=False
    )

    direccion: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    latitud: Mapped[float | None] = mapped_column(
        Numeric(9, 6),
        nullable=True
    )

    longitud: Mapped[float | None] = mapped_column(
        Numeric(9, 6),
        nullable=True
    )

    capacidad: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    # Hasta cuándo puede inscribirse el público. Nulo: hasta que el evento
    # empiece.
    fecha_limite_inscripcion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Con cuántos días de anticipación al inicio se cierra la cancelación de
    # la propia inscripción. Nulo o 0: se puede cancelar hasta que empiece.
    dias_limite_cancelacion: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    creado_por: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    # Control de edición concurrente: sube con cada cambio del evento o de
    # su cronograma. Quien guarda con una versión vieja recibe un 409.
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1"
    )
