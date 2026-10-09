from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field

from src.core.schemas.fields import Email
from src.core.schemas.fields import PersonName
from src.core.schemas.fields import Phone


class LoginRequest(BaseModel):
    correo: EmailStr
    contrasena: str


class RegisterRequest(BaseModel):
    nombre: PersonName
    apellido: PersonName
    correo: Email
    contrasena: str = Field(..., min_length=8, max_length=20)
    telefono: Phone | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
