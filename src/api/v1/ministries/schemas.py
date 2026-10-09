from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from src.core.schemas.fields import trimmed_text

MinistryName = trimmed_text(1, 255)


class MinistryCreate(BaseModel):
    nombre: MinistryName
    descripcion: str | None = Field(default=None, max_length=255)


class MinistryUpdate(BaseModel):
    nombre: MinistryName | None = None
    descripcion: str | None = Field(default=None, max_length=255)


class MinistryResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    nombre: str
    descripcion: str | None


class MinistryMemberResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    nombre: str
    apellido: str | None
    correo: str
