"""allow self-assigned invitations in estado_envio check

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-11 02:40:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLA = "invitaciones_participacion"
NOMBRE = "ck_invitaciones_estado_envio"


def upgrade() -> None:
    # El administrador puede asignarse a sí mismo una actividad: esa
    # invitación nace con `estado_envio = 'autoasignada'` (no hay correo).
    # La restricción original no lo admitía y el alta fallaba con un 500.
    op.drop_constraint(NOMBRE, TABLA, type_="check")
    op.create_check_constraint(
        NOMBRE,
        TABLA,
        "estado_envio IN ('en_cola', 'enviada', 'error', 'autoasignada')"
    )


def downgrade() -> None:
    # Las autoasignaciones no caben en la restricción anterior: se dejan
    # como enviadas (siguen aceptadas) para poder volver a crearla.
    op.execute(
        f"UPDATE {TABLA} SET estado_envio = 'enviada' "
        "WHERE estado_envio = 'autoasignada'"
    )
    op.drop_constraint(NOMBRE, TABLA, type_="check")
    op.create_check_constraint(
        NOMBRE,
        TABLA,
        "estado_envio IN ('en_cola', 'enviada', 'error')"
    )
