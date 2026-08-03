from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.core.constants.enums import UserRole
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

    contrasena: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    telefono: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    rol: Mapped[UserRole] = mapped_column(
        SQLAlchemyEnum(
            UserRole,
            name="user_role",
            native_enum=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            length=50
        ),
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