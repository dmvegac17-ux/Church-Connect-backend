from uuid import UUID

from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base


class MinistryModel(Base):
    __tablename__ = "ministry"

    id: Mapped[UUID] = mapped_column(
        primary_key=True
    )

    nombre: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
