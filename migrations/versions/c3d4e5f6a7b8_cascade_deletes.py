"""set ON DELETE CASCADE on all foreign keys to prevent orphaned rows

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (constraint_name, table, column, ref_table, ref_column)
FOREIGN_KEYS = [
    ("archivos_subido_por_fkey", "archivos", "subido_por", "usuarios", "id"),
    ("asistencias_usuario_id_fkey", "asistencias", "usuario_id", "usuarios", "id"),
    ("asistencias_evento_id_fkey", "asistencias", "evento_id", "event", "id"),
    (
        "confirmaciones_whatsapp_evento_id_fkey",
        "confirmaciones_email", "evento_id", "event", "id"
    ),
    (
        "confirmaciones_whatsapp_usuario_id_fkey",
        "confirmaciones_email", "usuario_id", "usuarios", "id"
    ),
    ("cronogramas_evento_id_fkey", "cronogramas", "evento_id", "event", "id"),
    (
        "inscripciones_usuario_id_fkey",
        "inscripciones", "usuario_id", "usuarios", "id"
    ),
    ("inscripciones_evento_id_fkey", "inscripciones", "evento_id", "event", "id"),
    (
        "notificaciones_usuario_id_fkey",
        "notificaciones", "usuario_id", "usuarios", "id"
    ),
    (
        "usuarios_ministerios_ministerio_id_fkey",
        "usuarios_ministry", "ministerio_id", "ministry", "id"
    ),
    (
        "usuarios_ministerios_usuario_id_fkey",
        "usuarios_ministry", "usuario_id", "usuarios", "id"
    ),
]


def upgrade() -> None:
    for name, table, column, ref_table, ref_column in FOREIGN_KEYS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name, table, ref_table, [column], [ref_column],
            ondelete="CASCADE"
        )


def downgrade() -> None:
    for name, table, column, ref_table, ref_column in FOREIGN_KEYS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name, table, ref_table, [column], [ref_column],
            ondelete="NO ACTION"
        )
