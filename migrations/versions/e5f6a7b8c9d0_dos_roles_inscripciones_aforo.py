"""two roles, registration notes and capacity bookkeeping

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-09 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UNICA = "uq_inscripciones_usuario_evento"


def _ya_es_unica(bind) -> bool:
    """
    El esquema base nunca se versionó: la unicidad `(usuario_id, evento_id)`
    puede existir ya con otro nombre en algunas bases de datos.
    """
    inspector = sa.inspect(bind)
    objetivo = {"usuario_id", "evento_id"}

    unicas = inspector.get_unique_constraints("inscripciones")
    indices = [i for i in inspector.get_indexes("inscripciones") if i.get("unique")]

    return any(
        set(item["column_names"]) == objetivo
        for item in [*unicas, *indices]
    )


def upgrade() -> None:
    # «Participante» deja de ser un rol: es la situación de quien está
    # asignado a una actividad, y puede ser cualquier usuario.
    op.execute("UPDATE usuarios SET rol = 'MEMBER' WHERE rol = 'PARTICIPANT'")

    op.add_column(
        "inscripciones",
        sa.Column("inscrito_por", sa.UUID(), nullable=True)
    )
    op.add_column(
        "inscripciones",
        sa.Column("nota", sa.String(length=200), nullable=True)
    )
    op.create_foreign_key(
        "inscripciones_inscrito_por_fkey",
        "inscripciones", "usuarios", ["inscrito_por"], ["id"],
        ondelete="SET NULL"
    )

    if not _ya_es_unica(op.get_bind()):
        # Antes de exigir la unicidad se conserva la inscripción más antigua
        # de cada persona por evento.
        op.execute(
            """
            DELETE FROM inscripciones
            WHERE id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY usuario_id, evento_id
                        ORDER BY fecha_inscripcion ASC, id ASC
                    ) AS orden
                    FROM inscripciones
                ) duplicadas
                WHERE duplicadas.orden > 1
            )
            """
        )
        op.create_unique_constraint(
            _UNICA,
            "inscripciones",
            ["usuario_id", "evento_id"]
        )

    # Quien ya participa no debe ocupar además un cupo de público.
    op.execute(
        """
        DELETE FROM inscripciones
        WHERE EXISTS (
            SELECT 1 FROM cronogramas
            WHERE cronogramas.evento_id = inscripciones.evento_id
              AND cronogramas.responsable_id = inscripciones.usuario_id
        )
        """
    )

    op.add_column(
        "invitaciones_participacion",
        sa.Column(
            "reemplazo_inscripcion", sa.Boolean(), nullable=False,
            server_default=sa.text("false")
        )
    )


def downgrade() -> None:
    op.drop_column("invitaciones_participacion", "reemplazo_inscripcion")

    bind = op.get_bind()
    unicas = sa.inspect(bind).get_unique_constraints("inscripciones")
    if any(item["name"] == _UNICA for item in unicas):
        op.drop_constraint(_UNICA, "inscripciones", type_="unique")

    op.drop_constraint(
        "inscripciones_inscrito_por_fkey", "inscripciones", type_="foreignkey"
    )
    op.drop_column("inscripciones", "nota")
    op.drop_column("inscripciones", "inscrito_por")

    # No se restaura el rol PARTICIPANT ni las filas eliminadas: no queda
    # registro de quién lo tenía. Las autoasignaciones (`estado_envio =
    # 'autoasignada'`) siguen siendo texto válido para la columna.
