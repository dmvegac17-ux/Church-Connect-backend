"""split personal data from users into profiles

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-10-15 09:00:00.000000

Paso 1 de 2. Crea `perfiles`, copia ahí los datos personales y deja de
exigirlos en `usuarios`. Las columnas viejas NO se eliminan aquí: eso lo hace
la migración siguiente, cuando todo el código desplegado ya lee del perfil.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RESPALDO = "usuarios_respaldo_antes_de_perfiles"
# Tablas que solo debe tocar el backend. Con la seguridad por filas activa y
# sin políticas, la API pública de Supabase no puede leerlas ni escribirlas;
# el backend se conecta como dueño y no se ve afectado.
SOLO_BACKEND = (
    "perfiles",
    RESPALDO,
    "restablecimientos_contrasena",
    "invitaciones_participacion",
    "cambios_cronograma",
)


def upgrade() -> None:
    # Respaldo de la tabla tal como estaba, antes de tocar nada.
    op.execute(f"CREATE TABLE {RESPALDO} AS TABLE usuarios")

    op.create_table(
        "perfiles",
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("apellido", sa.String(length=255), nullable=True),
        sa.Column("telefono", sa.String(length=50), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("usuario_id"),
    )

    # Un perfil por cada usuario, con sus datos personales.
    op.execute(
        "INSERT INTO perfiles "
        "(usuario_id, nombre, apellido, telefono, creado_en, actualizado_en) "
        "SELECT id, nombre, apellido, telefono, now(), now() FROM usuarios"
    )

    conexion = op.get_bind()
    usuarios = conexion.execute(sa.text("SELECT count(*) FROM usuarios")).scalar_one()
    perfiles = conexion.execute(sa.text("SELECT count(*) FROM perfiles")).scalar_one()
    if usuarios != perfiles:
        raise RuntimeError(
            f"La copia no cuadra: {usuarios} usuarios y {perfiles} perfiles."
        )

    # El código nuevo ya no escribe estas columnas: dejan de ser obligatorias
    # hasta que la migración siguiente las elimine.
    op.alter_column("usuarios", "nombre", existing_type=sa.String(255), nullable=True)
    op.alter_column("usuarios", "apellido", existing_type=sa.String(255), nullable=True)

    for tabla in SOLO_BACKEND:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # Los datos vuelven a `usuarios` antes de quitar los perfiles.
    op.execute(
        "UPDATE usuarios u SET nombre = p.nombre, apellido = p.apellido, "
        "telefono = p.telefono FROM perfiles p WHERE p.usuario_id = u.id"
    )
    op.execute("UPDATE usuarios SET apellido = '' WHERE apellido IS NULL")
    op.alter_column("usuarios", "apellido", existing_type=sa.String(255), nullable=False)
    op.alter_column("usuarios", "nombre", existing_type=sa.String(255), nullable=False)
    op.drop_table("perfiles")
    op.execute(f"DROP TABLE IF EXISTS {RESPALDO}")
    # La seguridad por filas de las otras tablas se deja activa: quitarla
    # volvería a exponerlas en la API pública.
