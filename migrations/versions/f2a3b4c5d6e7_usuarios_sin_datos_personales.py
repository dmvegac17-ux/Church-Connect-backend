"""drop personal columns from users (they live in profiles)

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-10-15 09:30:00.000000

Paso 2 de 2. Aplicar SOLO cuando todo el backend desplegado ya use la tabla
`perfiles`: una versión anterior del código deja de funcionar al no encontrar
estas columnas. Reversible: `downgrade` las vuelve a crear con sus datos.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("usuarios", "nombre")
    op.drop_column("usuarios", "apellido")
    op.drop_column("usuarios", "telefono")


def downgrade() -> None:
    op.add_column("usuarios", sa.Column("nombre", sa.String(255), nullable=True))
    op.add_column("usuarios", sa.Column("apellido", sa.String(255), nullable=True))
    op.add_column("usuarios", sa.Column("telefono", sa.String(50), nullable=True))
    op.execute(
        "UPDATE usuarios u SET nombre = p.nombre, apellido = p.apellido, "
        "telefono = p.telefono FROM perfiles p WHERE p.usuario_id = u.id"
    )
