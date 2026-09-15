from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    PARTICIPANT = "PARTICIPANT"
    MEMBER = "MEMBER"


class EstadoConfirmacion(str, Enum):
    PENDIENTE = "PENDIENTE"
    CONFIRMADO = "CONFIRMADO"
    RECHAZADO = "RECHAZADO"
