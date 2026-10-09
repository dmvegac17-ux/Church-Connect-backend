from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import EmailStr
from pydantic import Field
from pydantic import field_validator

from src.core.constants.enums import UserRole
from src.core.schemas.fields import Email
from src.core.schemas.fields import PersonName
from src.core.schemas.fields import Phone


def _normalize_role(value: object) -> object:
    if isinstance(value, str):
        return value.upper()

    return value


class UserCreate(BaseModel):
    nombre: PersonName
    apellido: PersonName
    correo: Email
    contrasena: str = Field(..., min_length=8, max_length=20)
    telefono: Phone | None = None
    rol: UserRole
    activo: bool = True

    _normalize_rol = field_validator("rol", mode="before")(_normalize_role)


class UserUpdate(BaseModel):
    nombre: PersonName | None = None
    apellido: PersonName | None = None
    correo: Email | None = None
    contrasena: str | None = Field(None, min_length=8, max_length=20)
    telefono: Phone | None = None
    rol: UserRole | None = None
    activo: bool | None = None

    _normalize_rol = field_validator("rol", mode="before")(_normalize_role)


class UserResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    nombre: str
    apellido: str | None
    correo: EmailStr
    telefono: str | None
    rol: UserRole
    activo: bool | None
    fecha_creacion: datetime | None


class UserListResponse(BaseModel):
    total: int
    items: list[UserResponse]