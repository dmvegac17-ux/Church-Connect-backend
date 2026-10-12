"""schedule changes: reconfirmation, soft delete, history and event version

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Control de edición concurrente: sube con cada cambio del evento o de
    # su cronograma.
    op.add_column(
        "event",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )

    # Borrado lógico: una actividad eliminada se conserva como cancelada
    # para el historial y para quien estaba asignado.
    op.add_column(
        "cronogramas",
        sa.Column("cancelada_en", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "cronogramas",
        sa.Column("cancelada_por", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_cronogramas_cancelada_por",
        "cronogramas", "usuarios",
        ["cancelada_por"], ["id"],
        ondelete="SET NULL"
    )

    # Reconfirmación: la actividad cambió después de que el responsable la
    # confirmó. `confirmado` guarda lo que había aceptado.
    op.add_column(
        "invitaciones_participacion",
        sa.Column(
            "reconfirmacion", sa.Boolean(), nullable=False,
            server_default=sa.text("false")
        )
    )
    op.add_column(
        "invitaciones_participacion",
        sa.Column("confirmado", sa.JSON(), nullable=True)
    )
    op.add_column(
        "invitaciones_participacion",
        sa.Column("aviso_cambio_id", sa.Uuid(), nullable=True)
    )

    op.create_table(
        "cambios_cronograma",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evento_id", sa.Uuid(), nullable=False),
        sa.Column("actividad_id", sa.Uuid(), nullable=True),
        sa.Column("actividad", sa.String(length=150), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("antes", sa.JSON(), nullable=True),
        sa.Column("despues", sa.JSON(), nullable=True),
        sa.Column("autor_id", sa.Uuid(), nullable=True),
        sa.Column("autor_nombre", sa.String(length=200), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["evento_id"], ["event.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["actividad_id"], ["cronogramas.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["autor_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cambios_cronograma_evento",
        "cambios_cronograma", ["evento_id", "fecha"]
    )


def downgrade() -> None:
    op.drop_index("ix_cambios_cronograma_evento", table_name="cambios_cronograma")
    op.drop_table("cambios_cronograma")
    op.drop_column("invitaciones_participacion", "aviso_cambio_id")
    op.drop_column("invitaciones_participacion", "confirmado")
    op.drop_column("invitaciones_participacion", "reconfirmacion")
    # Las canceladas volverían a verse como actividades vigentes: se quitan.
    op.execute("DELETE FROM cronogramas WHERE cancelada_en IS NOT NULL")
    op.drop_constraint(
        "fk_cronogramas_cancelada_por", "cronogramas", type_="foreignkey"
    )
    op.drop_column("cronogramas", "cancelada_por")
    op.drop_column("cronogramas", "cancelada_en")
    op.drop_column("event", "version")
