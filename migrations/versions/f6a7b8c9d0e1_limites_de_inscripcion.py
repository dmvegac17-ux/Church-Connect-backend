"""registration deadline and cancellation limit for events

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-09 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ambas nulas: los eventos existentes conservan su comportamiento (se
    # inscribe y se cancela hasta que el evento empieza).
    op.add_column(
        "event",
        sa.Column(
            "fecha_limite_inscripcion", sa.DateTime(timezone=True), nullable=True
        )
    )
    op.add_column(
        "event",
        sa.Column("dias_limite_cancelacion", sa.Integer(), nullable=True)
    )
    op.create_check_constraint(
        "ck_event_dias_limite_cancelacion",
        "event",
        "dias_limite_cancelacion IS NULL OR "
        "(dias_limite_cancelacion >= 0 AND dias_limite_cancelacion <= 365)"
    )
    op.create_check_constraint(
        "ck_event_fecha_limite_inscripcion",
        "event",
        "fecha_limite_inscripcion IS NULL OR "
        "fecha_limite_inscripcion <= fecha_inicio"
    )


def downgrade() -> None:
    op.drop_constraint("ck_event_fecha_limite_inscripcion", "event", type_="check")
    op.drop_constraint("ck_event_dias_limite_cancelacion", "event", type_="check")
    op.drop_column("event", "dias_limite_cancelacion")
    op.drop_column("event", "fecha_limite_inscripcion")
