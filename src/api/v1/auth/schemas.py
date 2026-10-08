from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field


class LoginRequest(BaseModel):
    correo: EmailStr
    contrasena: str


class RegisterRequest(BaseModel):
    nombre: str
    apellido: str
    correo: EmailStr
    contrasena: str = Field(..., min_length=8, max_length=20)
    telefono: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
