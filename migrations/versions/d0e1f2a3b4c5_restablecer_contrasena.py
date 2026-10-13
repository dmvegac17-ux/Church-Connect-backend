"""password reset requests and session cut-off

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-10-14 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Las sesiones iniciadas antes de esta fecha quedan cerradas.
    op.add_column(
        "usuarios",
        sa.Column("contrasena_cambiada_en", sa.DateTime(timezone=True), nullable=True)
    )

    op.create_table(
        "restablecimientos_contrasena",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        # Solo el hash (SHA-256): el token no se guarda.
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_restablecimientos_contrasena_token_hash",
        "restablecimientos_contrasena", ["token_hash"], unique=True
    )
    op.create_index(
        "ix_restablecimientos_usuario",
        "restablecimientos_contrasena", ["usuario_id", "creado_en"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_restablecimientos_usuario", table_name="restablecimientos_contrasena"
    )
    op.drop_index(
        "ix_restablecimientos_contrasena_token_hash",
        table_name="restablecimientos_contrasena"
    )
    op.drop_table("restablecimientos_contrasena")
    op.drop_column("usuarios", "contrasena_cambiada_en")
