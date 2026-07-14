from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import String, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base


class ScheduleModel(Base):
    __tablename__ = "cronogramas"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    evento_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False
    )

    actividad: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    hora_inicio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    hora_fin: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    responsable: Mapped[str] = mapped_column(
        String,
        nullable=False
    )