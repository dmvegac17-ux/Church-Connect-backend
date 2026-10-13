"""enable row level security on alembic_version

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-10-16 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Era la única tabla del esquema público sin seguridad por filas: la API
    # pública de Supabase podía leerla y modificarla. Con ella activa y sin
    # políticas queda cerrada; Alembic se conecta como dueño de la tabla y
    # sigue leyendo y escribiendo la versión sin cambios.
    op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")
