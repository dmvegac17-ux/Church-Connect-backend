from uuid import UUID

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class UserMinistryModel(Base):
    __tablename__ = "usuarios_ministry"

    id: Mapped[UUID] = mapped_column(
        primary_key=True
    )

    usuario_id: Mapped[UUID | None] = mapped_column(
        nullable=True
    )

    ministerio_id: Mapped[UUID | None] = mapped_column(
        nullable=True
    )
