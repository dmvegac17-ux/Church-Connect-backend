from uuid import UUID

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
    # Las versiones de los documentos legales que la persona vio y acepta.
    # Deben ser exactamente las vigentes: sin ellas no se crea la cuenta.
    documentos_aceptados: list[UUID] = Field(default_factory=list, max_length=10)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    correo: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=200)
    # Mismas reglas que al registrarse.
    contrasena: str = Field(..., min_length=8, max_length=20)
