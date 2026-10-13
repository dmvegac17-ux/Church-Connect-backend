"""add participation invitations and schedule responsible user

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACTIVA = "estado_respuesta IN ('pendiente', 'aceptada')"


def upgrade() -> None:
    # Nullable: los cronogramas anteriores guardan el responsable como texto
    # libre y no tienen un usuario asociado.
    op.add_column(
        "cronogramas",
        sa.Column("responsable_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "cronogramas_responsable_id_fkey",
        "cronogramas", "usuarios", ["responsable_id"], ["id"],
        ondelete="SET NULL"
    )

    op.create_table(
        "invitaciones_participacion",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("actividad_id", sa.UUID(), nullable=False),
        sa.Column("participante_id", sa.UUID(), nullable=False),
        sa.Column(
            "estado_respuesta", sa.String(length=20), nullable=False,
            server_default="pendiente"
        ),
        sa.Column("estado_previo", sa.String(length=20), nullable=True),
        sa.Column(
            "estado_envio", sa.String(length=20), nullable=False,
            server_default="en_cola"
        ),
        sa.Column("fecha_envio", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "intentos_envio", sa.Integer(), nullable=False,
            server_default="0"
        ),
        sa.Column("ultimo_error_envio", sa.Text(), nullable=True),
        sa.Column(
            "fecha_limite_respuesta", sa.DateTime(timezone=True),
            nullable=True
        ),
        sa.Column(
            "fecha_respuesta", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("motivo_rechazo", sa.String(length=255), nullable=True),
        sa.Column("invitada_por", sa.UUID(), nullable=True),
        sa.Column("cancelada_por", sa.UUID(), nullable=True),
        sa.Column(
            "fecha_cancelacion", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("revocada_por", sa.UUID(), nullable=True),
        sa.Column(
            "fecha_revocacion", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "notificacion_revocacion_estado", sa.String(length=20),
            nullable=True
        ),
        sa.Column("reemplaza_invitacion_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["actividad_id"], ["cronogramas.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["participante_id"], ["usuarios.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["invitada_por"], ["usuarios.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["cancelada_por"], ["usuarios.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["revocada_por"], ["usuarios.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["reemplaza_invitacion_id"], ["invitaciones_participacion.id"],
            ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "estado_respuesta IN ('pendiente', 'aceptada', 'rechazada', "
            "'vencida', 'cancelada', 'reasignada', 'revocada')",
            name="ck_invitaciones_estado_respuesta"
        ),
        sa.CheckConstraint(
            "estado_envio IN ('en_cola', 'enviada', 'error')",
            name="ck_invitaciones_estado_envio"
        ),
        sa.CheckConstraint(
            "motivo_rechazo IS NULL OR estado_respuesta = 'rechazada' "
            "OR estado_previo = 'rechazada'",
            name="ck_invitaciones_motivo_solo_rechazo"
        ),
        sa.CheckConstraint(
            "motivo_rechazo IS NULL OR length(motivo_rechazo) <= 255",
            name="ck_invitaciones_motivo_length"
        ),
    )

    # Como máximo una invitación activa por actividad, sin importar el
    # participante.
    op.create_index(
        "uq_invitacion_activa_por_actividad",
        "invitaciones_participacion", ["actividad_id"],
        unique=True,
        postgresql_where=sa.text(_ACTIVA)
    )
    op.create_index(
        "ix_invitaciones_participante_estado",
        "invitaciones_participacion", ["participante_id", "estado_respuesta"]
    )
    op.create_index(
        "ix_invitaciones_actividad",
        "invitaciones_participacion", ["actividad_id"]
    )
    op.create_index(
        "ix_invitaciones_estado_envio",
        "invitaciones_participacion", ["estado_envio"]
    )
    op.create_index(
        "ix_invitaciones_fecha_limite",
        "invitaciones_participacion", ["fecha_limite_respuesta"]
    )


def downgrade() -> None:
    op.drop_table("invitaciones_participacion")
    op.drop_constraint(
        "cronogramas_responsable_id_fkey", "cronogramas", type_="foreignkey"
    )
    op.drop_column("cronogramas", "responsable_id")
