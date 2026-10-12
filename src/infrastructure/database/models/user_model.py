from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import String
from sqlalchemy import select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from src.core.constants.enums import UserRole
from src.infrastructure.database.base import Base
from src.infrastructure.database.models.perfil_model import PerfilModel


class UserModel(Base):
    """
    La cuenta: con qué se entra (correo, contraseña), qué puede hacer (rol)
    y si está activa. Los datos personales viven en `perfiles`, uno a uno.

    `nombre`, `apellido` y `telefono` se siguen leyendo y escribiendo desde
    aquí (`usuario.nombre`), pero se guardan en el perfil: el resto del
    código no necesita saber en qué tabla están.
    """

    __tablename__ = "usuarios"

    id: Mapped[UUID] = mapped_column(
        primary_key=True
    )

    correo: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )

    contrasena: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    rol: Mapped[UserRole] = mapped_column(
        SQLAlchemyEnum(
            UserRole,
            name="user_role",
            native_enum=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            length=50
        ),
        nullable=False
    )

    activo: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True
    )

    fecha_creacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    

    # Última vez que se restableció la contraseña: las sesiones iniciadas
    # antes quedan cerradas.
    contrasena_cambiada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Siempre llega con el usuario, en la misma consulta (sin N+1).
    perfil: Mapped[PerfilModel | None] = relationship(
        PerfilModel,
        back_populates="usuario",
        uselist=False,
        lazy="joined",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    def _perfil(self) -> PerfilModel:
        """El perfil de la cuenta; lo crea con ella si todavía no existe."""
        if self.perfil is None:
            self.perfil = PerfilModel()

        return self.perfil

    # ── Datos personales: se guardan en `perfiles` ──────────────────────

    @hybrid_property
    def nombre(self) -> str | None:
        return self.perfil.nombre if self.perfil else None

    @nombre.inplace.setter
    def _set_nombre(self, valor: str) -> None:
        self._perfil().nombre = valor

    @nombre.inplace.expression
    @classmethod
    def _nombre_sql(cls):
        return (
            select(PerfilModel.nombre)
            .where(PerfilModel.usuario_id == cls.id)
            .scalar_subquery()
        )

    @hybrid_property
    def apellido(self) -> str | None:
        return self.perfil.apellido if self.perfil else None

    @apellido.inplace.setter
    def _set_apellido(self, valor: str | None) -> None:
        self._perfil().apellido = valor

    @apellido.inplace.expression
    @classmethod
    def _apellido_sql(cls):
        return (
            select(PerfilModel.apellido)
            .where(PerfilModel.usuario_id == cls.id)
            .scalar_subquery()
        )

    @hybrid_property
    def telefono(self) -> str | None:
        return self.perfil.telefono if self.perfil else None

    @telefono.inplace.setter
    def _set_telefono(self, valor: str | None) -> None:
        self._perfil().telefono = valor

    @telefono.inplace.expression
    @classmethod
    def _telefono_sql(cls):
        return (
            select(PerfilModel.telefono)
            .where(PerfilModel.usuario_id == cls.id)
            .scalar_subquery()
        )
