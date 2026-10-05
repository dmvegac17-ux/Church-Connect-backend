from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base


class ScheduleModel(Base):
    __tablename__ = "cronogramas"
    __table_args__ = (
        CheckConstraint(
            "descripcion IS NULL OR char_length(descripcion) <= 1000",
            name="ck_cronogramas_descripcion_length"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    evento_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("event.id", ondelete="CASCADE"),
        nullable=False
    )

    actividad: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    hora_inicio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    hora_fin: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    responsable: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )