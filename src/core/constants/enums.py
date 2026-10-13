from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class EstadoConfirmacion(str, Enum):
    PENDIENTE = "PENDIENTE"
    CONFIRMADO = "CONFIRMADO"
    RECHAZADO = "RECHAZADO"


class EstadoRespuestaInvitacion(str, Enum):
    PENDIENTE = "pendiente"
    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"
    VENCIDA = "vencida"
    CANCELADA = "cancelada"
    REASIGNADA = "reasignada"
    REVOCADA = "revocada"


class EstadoEnvioInvitacion(str, Enum):
    EN_COLA = "en_cola"
    ENVIADA = "enviada"
    ERROR = "error"
    # El administrador se asignó a sí mismo: no hay correo que enviar.
    AUTOASIGNADA = "autoasignada"
