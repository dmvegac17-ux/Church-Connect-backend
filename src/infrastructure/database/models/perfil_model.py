from datetime import UTC
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.infrastructure.database.base import Base


def _ahora() -> datetime:
    return datetime.now(UTC)


class PerfilModel(Base):
    """
    Datos personales de una persona, uno a uno con su cuenta (`usuarios`).

    La cuenta guarda lo que sirve para entrar (correo, contraseña, rol,
    estado); aquí va quién es. Las demás tablas siguen apuntando a
    `usuarios`. Para agregar un dato personal nuevo (cumpleaños, foto,
    dirección…) se añade una columna aquí, sin tocar `usuarios`: ver
    `docs/perfiles.md`.
    """

    __tablename__ = "perfiles"

    # La misma clave del usuario: garantiza un solo perfil por cuenta.
    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        primary_key=True
    )

    nombre: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    apellido: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    telefono: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_ahora
    )

    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_ahora,
        onupdate=_ahora
    )

    usuario = relationship(
        "UserModel",
        back_populates="perfil"
    )
