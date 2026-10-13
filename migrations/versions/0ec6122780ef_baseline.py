"""baseline (schema already applied, history was never committed)

Revision ID: 0ec6122780ef
Revises:
Create Date: 2026-10-04 00:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "0ec6122780ef"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op: este id ya estaba grabado en `alembic_version` de las bases de
    # datos existentes antes de que el historial de migraciones se empezara
    # a commitear al repositorio. Sirve solo como punto de partida para que
    # las revisiones nuevas puedan encadenarse correctamente.
    pass


def downgrade() -> None:
    pass
