"""cleanup after the profiles split: wrong unique key and backup tables

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-10-15 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RESPALDOS = (
    "usuarios_respaldo_antes_de_perfiles",
    "notificaciones_respaldo_antes_de_perfiles",
    "usuarios_ministry_respaldo_antes_de_perfiles",
)


def upgrade() -> None:
    # Restricción única mal puesta: se llamaba «rol» pero estaba sobre la
    # columna de la contraseña. No protegía nada: dos hashes nunca coinciden,
    # y dos personas pueden elegir la misma contraseña.
    op.execute("ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_rol_key")

    # Respaldos de la separación en usuarios y perfiles: ya verificada.
    for tabla in RESPALDOS:
        op.execute(f"DROP TABLE IF EXISTS {tabla}")


def downgrade() -> None:
    # Nada que restaurar: la restricción era un error y los respaldos eran
    # copias temporales de datos que ya no existen.
    pass
