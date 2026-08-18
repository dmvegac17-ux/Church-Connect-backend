from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class MinistryCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=255)
    descripcion: str | None = None


class MinistryUpdate(BaseModel):
    nombre: str | None = Field(None, min_length=1, max_length=255)
    descripcion: str | None = None


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
