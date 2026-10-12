from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class AnnouncementModel(Base):
    """
    Aviso general tipo cartelera, visible para cualquier usuario con sesión.

    `imagen_path` es la ruta de la imagen dentro del bucket de Storage; las
    imágenes externas anteriores a la subida de archivos solo tienen
    `imagen_url`.
    """

    __tablename__ = "announcements"
    __table_args__ = (
        Index(
            "ix_announcements_fecha_publicacion",
            text("fecha_publicacion DESC")
        ),
    )

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

    imagen_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Nulo si el autor ya no existe: el anuncio se conserva.
    publicado_por: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    fecha_publicacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    actualizado_por: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    fecha_actualizacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
