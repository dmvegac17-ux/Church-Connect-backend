"""announcements: authorship with FKs, update tracking and stored images

Revision ID: d7e8f9a0b1c2
Revises: c5d6e7f8a9b0
Create Date: 2026-10-12 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


def upgrade() -> None:
    # `publicado_por` era varchar sin relación. Lo que no sea el id de un
    # usuario existente se deja en NULL para que la conversión no falle (hoy
    # el único anuncio apunta a un administrador válido y se conserva).
    op.alter_column("announcements", "publicado_por", nullable=True)
    op.execute(
        f"""
        UPDATE announcements
        SET publicado_por = NULL
        WHERE publicado_por IS NOT NULL
          AND (
            publicado_por !~ '{_UUID}'
            OR NOT EXISTS (
              SELECT 1 FROM usuarios u WHERE u.id::text = lower(publicado_por)
            )
          )
        """
    )
    op.alter_column(
        "announcements",
        "publicado_por",
        type_=sa.UUID(),
        postgresql_using="publicado_por::uuid",
        existing_nullable=True
    )
    # Si se elimina el usuario, el anuncio se conserva sin autor.
    op.create_foreign_key(
        "announcements_publicado_por_fkey",
        "announcements", "usuarios", ["publicado_por"], ["id"],
        ondelete="SET NULL"
    )

    op.add_column(
        "announcements",
        sa.Column("actualizado_por", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "announcements_actualizado_por_fkey",
        "announcements", "usuarios", ["actualizado_por"], ["id"],
        ondelete="SET NULL"
    )
    # NULL = nunca se editó. La fija el backend en cada edición.
    op.add_column(
        "announcements",
        sa.Column(
            "fecha_actualizacion", sa.DateTime(timezone=True), nullable=True
        )
    )
    # Ruta dentro del bucket: permite borrar o reemplazar la imagen. Las
    # imágenes externas anteriores conservan `imagen_url` sin ruta.
    op.add_column(
        "announcements",
        sa.Column("imagen_path", sa.Text(), nullable=True)
    )

    op.create_index(
        "ix_announcements_fecha_publicacion",
        "announcements",
        [sa.text("fecha_publicacion DESC")]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_announcements_fecha_publicacion", table_name="announcements"
    )
    op.drop_column("announcements", "imagen_path")
    op.drop_column("announcements", "fecha_actualizacion")
    op.drop_constraint(
        "announcements_actualizado_por_fkey", "announcements",
        type_="foreignkey"
    )
    op.drop_column("announcements", "actualizado_por")
    op.drop_constraint(
        "announcements_publicado_por_fkey", "announcements",
        type_="foreignkey"
    )
    op.alter_column(
        "announcements",
        "publicado_por",
        type_=sa.String(),
        postgresql_using="publicado_por::text",
        existing_nullable=True
    )
    # El original era NOT NULL: los anuncios que quedaron sin autor (usuario
    # eliminado) no tienen a quién volver, así que se marcan como tal.
    op.execute(
        "UPDATE announcements SET publicado_por = 'desconocido' "
        "WHERE publicado_por IS NULL"
    )
    op.alter_column("announcements", "publicado_por", nullable=False)
