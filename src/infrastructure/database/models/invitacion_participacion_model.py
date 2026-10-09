from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base

_ACTIVA = "estado_respuesta IN ('pendiente', 'aceptada')"


class InvitacionParticipacionModel(Base):
    """
    Invitación a un participante para una actividad del cronograma.

    Una actividad acumula varias invitaciones a lo largo del tiempo, pero
    solo una puede estar activa (`pendiente` o `aceptada`): lo garantiza el
    índice único parcial `uq_invitacion_activa_por_actividad`. Los estados
    se guardan como texto (valores de `EstadoRespuestaInvitacion` y
    `EstadoEnvioInvitacion`), igual que el resto de enums del proyecto.
    """

    __tablename__ = "invitaciones_participacion"
    __table_args__ = (
        CheckConstraint(
            "motivo_rechazo IS NULL OR estado_respuesta = 'rechazada' "
            "OR estado_previo = 'rechazada'",
            name="ck_invitaciones_motivo_solo_rechazo"
        ),
        CheckConstraint(
            "motivo_rechazo IS NULL OR length(motivo_rechazo) <= 255",
            name="ck_invitaciones_motivo_length"
        ),
        Index(
            "uq_invitacion_activa_por_actividad",
            "actividad_id",
            unique=True,
            postgresql_where=text(_ACTIVA),
            sqlite_where=text(_ACTIVA)
        ),
        Index(
            "ix_invitaciones_participante_estado",
            "participante_id",
            "estado_respuesta"
        ),
        Index("ix_invitaciones_actividad", "actividad_id"),
        Index("ix_invitaciones_estado_envio", "estado_envio"),
        Index("ix_invitaciones_fecha_limite", "fecha_limite_respuesta"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4
    )

    actividad_id: Mapped[UUID] = mapped_column(
        ForeignKey("cronogramas.id", ondelete="CASCADE"),
        nullable=False
    )

    participante_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )

    estado_respuesta: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pendiente"
    )

    estado_previo: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    estado_envio: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="en_cola"
    )

    fecha_envio: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    intentos_envio: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    ultimo_error_envio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    fecha_limite_respuesta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    fecha_respuesta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    motivo_rechazo: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    invitada_por: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    cancelada_por: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    fecha_cancelacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    revocada_por: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    fecha_revocacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    notificacion_revocacion_estado: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    reemplaza_invitacion_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("invitaciones_participacion.id", ondelete="SET NULL"),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
