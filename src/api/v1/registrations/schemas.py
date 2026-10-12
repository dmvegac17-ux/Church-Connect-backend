from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class RegistrationCreate(BaseModel):
    evento_id: UUID
    # Solo administrador: inscribir a otra persona y dejar una nota.
    usuario_id: UUID | None = None
    nota: str | None = Field(default=None, max_length=200)


class RegistrationUpdate(BaseModel):
    nota: str | None = Field(default=None, max_length=200)


class RegistrationPerson(BaseModel):
    id: UUID
    nombre_completo: str
    correo: str


class RegistrationResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    usuario_id: UUID
    evento_id: UUID
    fecha_inscripcion: datetime
    # Administrador que hizo la inscripción; nulo si se inscribió la persona.
    inscrito_por: UUID | None = None
    nota: str | None = None
    usuario: RegistrationPerson | None = None
    inscrito_por_usuario: RegistrationPerson | None = None
    # Cupos que quedan para público justo después de inscribir.
    cupos_disponibles: int | None = None
