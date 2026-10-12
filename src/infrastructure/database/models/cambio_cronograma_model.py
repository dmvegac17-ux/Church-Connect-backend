from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class CambioCronogramaModel(Base):
    """
    Historial del cronograma: quién creó, editó o eliminó una actividad,
    cuándo, y qué valores tenía antes y después. Solo lo consulta el
    administrador.
    """

    __tablename__ = "cambios_cronograma"
    __table_args__ = (
        Index("ix_cambios_cronograma_evento", "evento_id", "fecha"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4
    )

    evento_id: Mapped[UUID] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"),
        nullable=False
    )

    actividad_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cronogramas.id", ondelete="SET NULL"),
        nullable=True
    )

    # Nombre de la actividad en ese momento: se conserva aunque cambie.
    actividad: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    # `creada`, `editada` o `eliminada`.
    tipo: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    # Solo los campos que cambiaron (todos al crear o eliminar).
    antes: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    despues: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    autor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    # Se conserva aunque la cuenta se elimine.
    autor_nombre: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
