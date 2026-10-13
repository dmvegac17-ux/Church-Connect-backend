from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class ScheduleCreate(BaseModel):
    evento_id: UUID
    actividad: str = Field(min_length=1, max_length=150)
    hora_inicio: datetime
    hora_fin: datetime
    responsable: str = Field(min_length=1, max_length=150)
    descripcion: str | None = Field(default=None, max_length=1000)


class ScheduleUpdate(BaseModel):
    actividad: str | None = Field(default=None, min_length=1, max_length=150)
    hora_inicio: datetime | None = None
    hora_fin: datetime | None = None
    responsable: str | None = Field(default=None, min_length=1, max_length=150)
    descripcion: str | None = Field(default=None, max_length=1000)


class ScheduleTimeItem(BaseModel):
    id: UUID
    hora_inicio: datetime
    hora_fin: datetime


class ScheduleTimesUpdate(BaseModel):
    """Horario nuevo de varias actividades del mismo evento."""

    evento_id: UUID
    items: list[ScheduleTimeItem] = Field(min_length=1, max_length=200)


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    evento_id: UUID
    actividad: str
    hora_inicio: datetime
    hora_fin: datetime
    responsable: str
    # Usuario con la invitación activa de la actividad (si la hay).
    responsable_id: UUID | None = None
    # Solo para miembros: `false` si `responsable` es un texto de «pendiente»
    # porque nadie confirmó todavía. El administrador siempre ve el nombre.
    responsable_confirmado: bool | None = None
    # Solo para el administrador: `confirmado`, `pendiente`,
    # `por_reconfirmar`, `rechazado`, `sin_respuesta`, `sin_asignar` o
    # `fuera_de_rango`.
    estado: str | None = None
    descripcion: str | None = None


class CambioCronogramaResponse(BaseModel):
    """Una entrada del historial del cronograma (solo administrador)."""

    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    actividad_id: UUID | None = None
    actividad: str
    # `creada`, `editada` o `eliminada`.
    tipo: str
    # Solo los campos que cambiaron.
    antes: dict | None = None
    despues: dict | None = None
    autor_nombre: str
    fecha: datetime


class EventoCronograma(BaseModel):
    id: UUID
    titulo: str
    fecha_inicio: datetime
    fecha_fin: datetime
    lugar: str


class ActividadConEstado(ScheduleResponse):
    estado: str


class CronogramaDeEvento(BaseModel):
    """Un evento con todas sus actividades, ordenadas por hora de inicio."""

    evento: EventoCronograma
    actividades: list[ActividadConEstado]
