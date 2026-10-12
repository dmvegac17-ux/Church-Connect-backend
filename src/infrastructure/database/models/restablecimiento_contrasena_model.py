from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class RestablecimientoContrasenaModel(Base):
    """
    Solicitud de restablecer la contraseña por correo.

    Se guarda solo el hash del token: quien lea la base no puede armar el
    enlace. Cada solicitud sirve una vez (`usado_en`) y vence pronto
    (`expira_en`).
    """

    __tablename__ = "restablecimientos_contrasena"
    __table_args__ = (
        # Solicitudes recientes de una persona (límite por hora).
        Index("ix_restablecimientos_usuario", "usuario_id", "creado_en"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4
    )

    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )

    # SHA-256 del token, en hexadecimal.
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True
    )

    expira_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    # Se usó para cambiar la contraseña, o quedó anulado por uno más nuevo.
    usado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
