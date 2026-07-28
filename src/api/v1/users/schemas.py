from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import EmailStr


class UserCreate(BaseModel):
    nombre: str
    apellido: str | None = None
    correo: EmailStr
    contrasena: str
    telefono: str | None = None
    rol: str
    activo: bool = True


class UserUpdate(BaseModel):
    nombre: str | None = None
    apellido: str | None = None
    correo: EmailStr | None = None
    contrasena: str | None = None
    telefono: str | None = None
    rol: str | None = None
    activo: bool | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    nombre: str
    apellido: str | None
    correo: EmailStr
    telefono: str | None
    rol: str
    activo: bool | None
    fecha_creacion: datetime | None


class UserListResponse(BaseModel):
    total: int
    items: list[UserResponse]