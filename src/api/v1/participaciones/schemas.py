from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field
from pydantic import StrictInt

from src.core.constants.enums import UserRole


# ── Peticiones ──────────────────────────────────────────────────────────

class RechazoRequest(BaseModel):
    motivo: str | None = Field(default=None, max_length=255)


class ReemplazoRequest(BaseModel):
    participante_id: UUID
    # Entero estricto: decimales, texto y vacío se rechazan con 422. El rango
    # depende de la fecha del evento y lo valida el servicio.
    dias_para_confirmar: StrictInt


class InvitacionCreate(ReemplazoRequest):
    actividad_id: UUID


# ── Respuestas compartidas ──────────────────────────────────────────────

class EventoRef(BaseModel):
    id: UUID
    nombre: str


class ActividadRef(BaseModel):
    id: UUID
    nombre: str
    # Fecha de la actividad en America/Bogota (`YYYY-MM-DD`).
    fecha: str
    hora_inicio: datetime
    hora_fin: datetime


class PersonaRef(BaseModel):
    id: UUID
    nombre_completo: str


# ── Participante ────────────────────────────────────────────────────────

class ActividadInvitacion(ActividadRef):
    lugar: str
    descripcion: str | None = None


class ResponsableRef(BaseModel):
    nombre: str
    area: str | None = None


class InvitacionPropia(BaseModel):
    """Sin datos de envío ni información administrativa."""

    id: UUID
    estado_respuesta: str
    fecha_invitacion: datetime
    fecha_limite_respuesta: datetime | None = None
    fecha_respuesta: datetime | None = None
    fecha_revocacion: datetime | None = None
    motivo_rechazo: str | None = None
    evento: EventoRef
    actividad: ActividadInvitacion
    responsable: ResponsableRef | None = None


class ConteosPropias(BaseModel):
    pendientes: int
    respondidas: int
    todas: int


class InvitacionesPropias(BaseModel):
    conteos: ConteosPropias
    items: list[InvitacionPropia]


# ── Administrador ───────────────────────────────────────────────────────

class ReemplazoRef(BaseModel):
    participante: PersonaRef
    fecha_limite_respuesta: datetime | None = None


class ParticipacionAdmin(BaseModel):
    id: UUID
    actividad: ActividadRef
    evento: EventoRef
    participante: PersonaRef
    estado_envio: str
    fecha_envio: datetime | None = None
    intentos_envio: int
    ultimo_error_envio: str | None = None
    estado_respuesta: str
    estado_previo: str | None = None
    fecha_respuesta: datetime | None = None
    fecha_limite_respuesta: datetime | None = None
    motivo_rechazo: str | None = None
    notificacion_revocacion_estado: str | None = None
    requiere_reasignacion: bool
    acciones_permitidas: list[str]
    reemplazo: ReemplazoRef | None = None


class ConteosAdmin(BaseModel):
    todas: int
    pendientes: int
    aceptadas: int
    por_reasignar: int
    error_envio: int


class AlertasAdmin(BaseModel):
    actividades_por_reasignar: int
    invitaciones_error_envio: int


class ParticipacionesAdmin(BaseModel):
    conteos: ConteosAdmin
    alertas: AlertasAdmin
    items: list[ParticipacionAdmin]


class ReemplazoResultado(BaseModel):
    original: ParticipacionAdmin
    nueva: ParticipacionAdmin


class DatosReasignacion(BaseModel):
    modo: str
    actividad: ActividadRef
    evento: EventoRef
    asignado_actual: PersonaRef
    motivo_liberacion: str
    motivo_rechazo: str | None = None
    dias_hasta_evento: int
    dias_para_confirmar_max: int


class ParticipanteElegible(BaseModel):
    id: UUID
    nombre_completo: str
    correo: str
    rol: UserRole
    cruce_horario: bool
