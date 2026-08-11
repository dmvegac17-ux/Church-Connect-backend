from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class AnnouncementModel(Base):
    __tablename__ = "anuncios"

    id: Mapped[UUID] = mapped_column(
        primary_key=True
    )

    titulo: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )

    contenido: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    imagen_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    publicado_por: Mapped[UUID] = mapped_column(
        nullable=False
    )

    fecha_publicacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )