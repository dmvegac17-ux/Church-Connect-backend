from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class ArchivosModel(Base):
    __tablename__ = "archivos"

    id: Mapped[UUID] = mapped_column(
        primary_key=True
    )

    nombre_archivo: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    url_archivo: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    tipo: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    subido_por: Mapped[UUID | None] = mapped_column(
        nullable=True
    )

    fecha_subida: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )