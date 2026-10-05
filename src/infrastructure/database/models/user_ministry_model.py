from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class UserMinistryModel(Base):
    __tablename__ = "usuarios_ministry"

    id: Mapped[UUID] = mapped_column(
        primary_key=True
    )

    usuario_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=True
    )

    ministerio_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ministry.id", ondelete="CASCADE"),
        nullable=True
    )
