from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from src.core.schemas.fields import trimmed_text

TipoDocumento = Literal["terminos", "privacidad"]


class DocumentoPublico(BaseModel):
    """La versión publicada, como la ve cualquiera (con o sin sesión)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tipo: str
    version: str
    titulo: str
    # Markdown.
    contenido: str
    publicado_en: datetime | None = None


class DocumentoPendiente(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tipo: str
    version: str
    titulo: str


class DocumentoAdmin(DocumentoPublico):
    # `borrador`, `publicado` o `archivado`.
    estado: str
    requiere_reaceptacion: bool
    publicado_por: UUID | None = None
    creado_por: UUID | None = None
    actualizado_por: UUID | None = None
    creado_en: datetime
    actualizado_en: datetime


class BorradorUpdate(BaseModel):
    titulo: trimmed_text(1, 200)
    contenido: str = Field(..., max_length=100_000)


class PublicarRequest(BaseModel):
    # `true`: cambio importante, todos vuelven a aceptar (sube a N.0).
    # `false`: corrección menor, nadie tiene que hacer nada (sube a N.M+1).
    requiere_reaceptacion: bool


class AceptarRequest(BaseModel):
    # Las versiones que la persona vio y acepta.
    documentos: list[UUID] = Field(default_factory=list, max_length=10)


class AceptacionPropia(BaseModel):
    id: UUID
    documento_id: UUID
    tipo: str
    titulo: str
    version: str
    aceptado_en: datetime


class EstadoAceptacion(BaseModel):
    version: str
    aceptado_en: datetime


class PersonaAceptaciones(BaseModel):
    usuario_id: UUID
    nombre_completo: str
    correo: str
    # Por tipo de documento: la aceptación vigente, o `null` si está pendiente.
    aceptaciones: dict[str, EstadoAceptacion | None]
    al_dia: bool


class ResumenAceptaciones(BaseModel):
    # Por tipo: la versión vigente.
    documentos: dict[str, dict[str, str]]
    total: int
    al_dia: int
    personas: list[PersonaAceptaciones]
