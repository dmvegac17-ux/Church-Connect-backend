from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, DateTime, Text
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
        # El cronograma de un evento, en orden de hora.
        Index("ix_cronogramas_evento_inicio", "evento_id", "hora_inicio"),
        # Aforo y participaciones: quién es responsable de qué.
        Index("ix_cronogramas_responsable", "responsable_id"),
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

    # Usuario asignado a la actividad. Se mantiene sincronizado con la
    # invitación activa (ver `ParticipacionService`); `responsable` conserva
    # el nombre visible para no romper los cronogramas anteriores.
    responsable_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Borrado lógico: una actividad eliminada se conserva como cancelada,
    # para el historial y para quien estaba asignado a ella.
    cancelada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    cancelada_por: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )
