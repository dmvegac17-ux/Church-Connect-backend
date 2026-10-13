from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Index
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class RegistrationModel(Base):
    """
    Inscripción de una persona como público de un evento. Los participantes
    (asignados a una actividad) no se inscriben: ya ocupan aforo.
    """

    __tablename__ = "inscripciones"
    __table_args__ = (
        UniqueConstraint(
            "usuario_id",
            "evento_id",
            name="uq_inscripciones_usuario_evento"
        ),
        # Inscritos de un evento: el índice único empieza por `usuario_id`
        # y no sirve para buscar por evento.
        Index("ix_inscripciones_evento", "evento_id"),
    )

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

    fecha_inscripcion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    # Administrador que inscribió a la persona; nulo si se inscribió ella misma.
    inscrito_por: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    nota: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True
    )
