from datetime import UTC
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from src.infrastructure.database.base import Base

TIPOS = ("terminos", "privacidad")
BORRADOR, PUBLICADO, ARCHIVADO = "borrador", "publicado", "archivado"


def _ahora() -> datetime:
    return datetime.now(UTC)


class DocumentoLegalModel(Base):
    """
    Una versión de los Términos y condiciones o de la Política de privacidad.

    Lo publicado nunca se modifica: es el texto que la gente aceptó. Un
    cambio es una versión nueva, que nace como borrador y al publicarse
    archiva a la anterior. La base garantiza una sola versión publicada y un
    solo borrador por tipo.
    """

    __tablename__ = "documentos_legales"
    __table_args__ = (
        UniqueConstraint(
            "tipo", "version_mayor", "version_menor",
            name="uq_documentos_legales_version"
        ),
        Index(
            "uq_documentos_legales_publicado",
            "tipo",
            unique=True,
            postgresql_where=text("estado = 'publicado'"),
            sqlite_where=text("estado = 'publicado'")
        ),
        Index(
            "uq_documentos_legales_borrador",
            "tipo",
            unique=True,
            postgresql_where=text("estado = 'borrador'"),
            sqlite_where=text("estado = 'borrador'")
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4
    )

    # `terminos` o `privacidad`.
    tipo: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    # Versión «mayor.menor». Sube la mayor cuando el cambio exige volver a
    # aceptar; la menor, cuando es una corrección que no lo exige.
    version_mayor: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    version_menor: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    titulo: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    # Texto en Markdown. Se guarda como texto y se escapa al mostrarlo: no
    # admite HTML ni scripts.
    contenido: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=BORRADOR
    )

    # Quien había aceptado la versión anterior debe aceptar esta.
    requiere_reaceptacion: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    publicado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    publicado_por: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    creado_por: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    actualizado_por: Mapped[UUID | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_ahora
    )

    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_ahora,
        onupdate=_ahora
    )

    @property
    def version(self) -> str:
        return f"{self.version_mayor}.{self.version_menor}"


class AceptacionDocumentoModel(Base):
    """
    Constancia de que una persona aceptó una versión concreta de un
    documento, y cuándo. Es un registro de cumplimiento: no se edita ni se
    borra (solo desaparece si se elimina la cuenta).
    """

    __tablename__ = "aceptaciones_documentos"
    __table_args__ = (
        UniqueConstraint(
            "usuario_id", "documento_id",
            name="uq_aceptaciones_usuario_documento"
        ),
        Index("ix_aceptaciones_usuario", "usuario_id"),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4
    )

    usuario_id: Mapped[UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False
    )

    # Un documento con aceptaciones no se puede eliminar.
    documento_id: Mapped[UUID] = mapped_column(
        ForeignKey("documentos_legales.id", ondelete="RESTRICT"),
        nullable=False
    )

    aceptado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_ahora
    )

    # Desde dónde se aceptó: refuerzan la constancia.
    ip: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True
    )
