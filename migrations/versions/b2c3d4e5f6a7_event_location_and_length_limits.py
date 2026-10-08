"""add event geolocation columns and character length limits

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "event",
        sa.Column("direccion", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "event",
        sa.Column("latitud", sa.Numeric(9, 6), nullable=True)
    )
    op.add_column(
        "event",
        sa.Column("longitud", sa.Numeric(9, 6), nullable=True)
    )

    op.alter_column(
        "event", "titulo",
        type_=sa.String(length=150),
        existing_type=sa.String(),
        existing_nullable=False
    )
    op.alter_column(
        "event", "lugar",
        type_=sa.String(length=200),
        existing_type=sa.String(),
        existing_nullable=False
    )
    op.alter_column(
        "cronogramas", "actividad",
        type_=sa.String(length=150),
        existing_type=sa.String(),
        existing_nullable=False
    )
    op.alter_column(
        "cronogramas", "responsable",
        type_=sa.String(length=150),
        existing_type=sa.String(),
        existing_nullable=False
    )

    op.create_check_constraint(
        "ck_event_descripcion_length",
        "event",
        "char_length(descripcion) <= 2000"
    )
    op.create_check_constraint(
        "ck_cronogramas_descripcion_length",
        "cronogramas",
        "descripcion IS NULL OR char_length(descripcion) <= 1000"
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_cronogramas_descripcion_length", "cronogramas", type_="check"
    )
    op.drop_constraint(
        "ck_event_descripcion_length", "event", type_="check"
    )

    op.alter_column(
        "cronogramas", "responsable",
        type_=sa.String(),
        existing_type=sa.String(length=150),
        existing_nullable=False
    )
    op.alter_column(
        "cronogramas", "actividad",
        type_=sa.String(),
        existing_type=sa.String(length=150),
        existing_nullable=False
    )
    op.alter_column(
        "event", "lugar",
        type_=sa.String(),
        existing_type=sa.String(length=200),
        existing_nullable=False
    )
    op.alter_column(
        "event", "titulo",
        type_=sa.String(),
        existing_type=sa.String(length=150),
        existing_nullable=False
    )

    op.drop_column("event", "longitud")
    op.drop_column("event", "latitud")
    op.drop_column("event", "direccion")
