from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class UserModel(Base):
    __tablename__ = "usuarios"

    id: Mapped[UUID] = mapped_column(
        primary_key=True
    )

    nombre: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )

    apellido: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    correo: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )

    telefono: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    rol: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    activo: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True
    )

    fecha_creacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )