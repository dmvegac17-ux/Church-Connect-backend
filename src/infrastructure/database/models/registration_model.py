from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class RegistrationModel(Base):
    __tablename__ = "inscripciones"

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
