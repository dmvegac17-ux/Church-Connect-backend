from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


# Tope de negocio del aforo: 10 millones cubre los encuentros multitudinarios
# más grandes (concentraciones internacionales de varios millones de
# personas) y descarta los errores de tecleo. Queda muy por debajo del
# máximo de la columna `event.capacidad` (`INTEGER` de 32 bits,
# 2.147.483.647), así que la base de datos nunca rechaza un valor válido.
CAPACIDAD_MAX = 10_000_000

# Días de anticipación con que se cierra la cancelación de una inscripción.
DIAS_LIMITE_CANCELACION_MAX = 365


class EventCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=150)
    descripcion: str = Field(min_length=1, max_length=2000)
    fecha_inicio: datetime
    fecha_fin: datetime
    lugar: str = Field(min_length=1, max_length=200)
    direccion: str | None = Field(default=None, max_length=255)
    latitud: float | None = Field(default=None, ge=-90, le=90)
    longitud: float | None = Field(default=None, ge=-180, le=180)
    capacidad: int = Field(gt=0, le=CAPACIDAD_MAX)
    # Hasta cuándo se puede inscribir el público (no posterior al inicio).
    fecha_limite_inscripcion: datetime | None = None
    # Días antes del inicio en que deja de poder cancelarse la inscripción.
    dias_limite_cancelacion: int | None = Field(
        default=None, ge=0, le=DIAS_LIMITE_CANCELACION_MAX
    )


class ActividadAjuste(BaseModel):
    """Qué hacer con una actividad al cambiar el horario de su evento."""

    id: UUID
    # Horario nuevo; lo que no venga se conserva.
    hora_inicio: datetime | None = None
    hora_fin: datetime | None = None
    # Nunca se elimina una actividad sin pedirlo.
    eliminar: bool = False


class EventUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=150)
    descripcion: str | None = Field(default=None, min_length=1, max_length=2000)
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    lugar: str | None = Field(default=None, min_length=1, max_length=200)
    direccion: str | None = Field(default=None, max_length=255)
    latitud: float | None = Field(default=None, ge=-90, le=90)
    longitud: float | None = Field(default=None, ge=-180, le=180)
    capacidad: int | None = Field(default=None, gt=0, le=CAPACIDAD_MAX)
    # `null` explícito quita el límite.
    fecha_limite_inscripcion: datetime | None = None
    dias_limite_cancelacion: int | None = Field(
        default=None, ge=0, le=DIAS_LIMITE_CANCELACION_MAX
    )
    # Versión que cargó el formulario: si ya no es la vigente, 409.
    version: int | None = Field(default=None, ge=1)
    # Ajustes al cronograma que se guardan junto con el evento (todo o nada).
    actividades: list[ActividadAjuste] | None = Field(default=None, max_length=200)


class EventAforo(BaseModel):
    """
    Ocupación del evento. El miembro solo recibe su cupo (aforo menos
    participantes) y los disponibles; las cifras internas van en `None`.
    """

    # Aforo total menos participantes.
    cupo_publico: int
    # Lugares libres para público; nunca negativo.
    disponibles: int
    # Solo administrador.
    participantes: int | None = None
    publico: int | None = None
    ocupados: int | None = None
    sobrecupo: int | None = None
    # Situación del usuario autenticado frente al evento.
    inscrito: bool = False
    inscripcion_id: UUID | None = None
    participa: bool = False
    inscripcion_reemplazada: bool = False
    # Quien consulta ya no puede inscribirse: el evento empezó o, para el
    # público, pasó la fecha límite de inscripción.
    inscripciones_cerradas: bool = False
    # Quien consulta ya no puede cancelar su inscripción: pasó el límite de
    # días o el evento empezó. Un administrador siempre puede.
    cancelacion_cerrada: bool = False


class EventResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    # Sube con cada cambio del evento o de su cronograma.
    version: int = 1
    titulo: str
    descripcion: str
    fecha_inicio: datetime
    fecha_fin: datetime
    lugar: str
    direccion: str | None = None
    latitud: float | None = None
    longitud: float | None = None
    # Aforo total para el administrador; para el miembro, su cupo (el aforo
    # total y el número de participantes no se le exponen).
    capacidad: int
    fecha_limite_inscripcion: datetime | None = None
    dias_limite_cancelacion: int | None = None
    # Calculada: inicio menos `dias_limite_cancelacion`. Hasta ese instante el
    # público puede cancelar su inscripción.
    fecha_limite_cancelacion: datetime
    creado_por: str
    total_actividades: int = 0
    aforo: EventAforo
