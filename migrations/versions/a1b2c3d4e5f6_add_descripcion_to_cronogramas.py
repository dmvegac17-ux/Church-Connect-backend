"""add descripcion to cronogramas

Revision ID: a1b2c3d4e5f6
Revises: 0ec6122780ef
Create Date: 2026-10-04 00:00:00.000001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "0ec6122780ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cronogramas",
        sa.Column("descripcion", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("cronogramas", "descripcion")
