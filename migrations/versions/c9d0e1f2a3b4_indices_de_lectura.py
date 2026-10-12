"""indexes for the most frequent reads

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-10-13 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # La bandeja de cada persona, ordenada por fecha.
    op.create_index(
        "ix_notificaciones_usuario_fecha",
        "notificaciones", ["usuario_id", "fecha_envio"]
    )
    # Contador de no leídas y «marcar todas»: solo las pendientes.
    op.create_index(
        "ix_notificaciones_no_leidas",
        "notificaciones", ["usuario_id"],
        postgresql_where=sa.text("leida = false")
    )
    # El cronograma de un evento, en orden de hora.
    op.create_index(
        "ix_cronogramas_evento_inicio",
        "cronogramas", ["evento_id", "hora_inicio"]
    )
    # Aforo y participaciones: quién es responsable de qué.
    op.create_index(
        "ix_cronogramas_responsable",
        "cronogramas", ["responsable_id"]
    )
    # Inscritos de un evento (el índice único empieza por usuario_id).
    op.create_index(
        "ix_inscripciones_evento",
        "inscripciones", ["evento_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_inscripciones_evento", table_name="inscripciones")
    op.drop_index("ix_cronogramas_responsable", table_name="cronogramas")
    op.drop_index("ix_cronogramas_evento_inicio", table_name="cronogramas")
    op.drop_index("ix_notificaciones_no_leidas", table_name="notificaciones")
    op.drop_index("ix_notificaciones_usuario_fecha", table_name="notificaciones")
