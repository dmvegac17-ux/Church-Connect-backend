from pydantic import BaseModel
from pydantic import EmailStr


class LoginRequest(BaseModel):
    correo: EmailStr
    contrasena: str


class RegisterRequest(BaseModel):
    nombre: str
    apellido: str
    correo: EmailStr
    contrasena: str
    telefono: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
