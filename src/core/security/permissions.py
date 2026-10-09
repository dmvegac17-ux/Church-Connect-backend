from enum import Enum
from uuid import UUID

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from src.api.dependencies.auth import get_current_user
from src.core.constants.enums import UserRole
from src.infrastructure.database.models.user_model import UserModel


class Permission(str, Enum):
    PARTICIPACIONES_VER_PROPIAS = "participaciones.ver_propias"
    PARTICIPACIONES_RESPONDER_PROPIAS = "participaciones.responder_propias"
    PARTICIPACIONES_SUPERVISAR = "participaciones.supervisar"
    PARTICIPACIONES_CANCELAR = "participaciones.cancelar"
    PARTICIPACIONES_REENVIAR = "participaciones.reenviar"
    PARTICIPACIONES_REASIGNAR = "participaciones.reasignar"


# El miembro no tiene permisos de participaciones. El resto de sus accesos
# sigue validándose por rol con `require_roles`, donde PARTICIPANT ya figura
# en todos los endpoints abiertos a MEMBER.
_MEMBER_PERMISSIONS: frozenset[Permission] = frozenset()

# El participante es el miembro más la confirmación de sus invitaciones: se
# compone a partir del conjunto del miembro, no se copia a mano.
_PARTICIPANT_PERMISSIONS: frozenset[Permission] = _MEMBER_PERMISSIONS | {
    Permission.PARTICIPACIONES_VER_PROPIAS,
    Permission.PARTICIPACIONES_RESPONDER_PROPIAS,
}

# El administrador supervisa, pero no recibe ni responde invitaciones.
_ADMIN_PERMISSIONS: frozenset[Permission] = _MEMBER_PERMISSIONS | {
    Permission.PARTICIPACIONES_SUPERVISAR,
    Permission.PARTICIPACIONES_CANCELAR,
    Permission.PARTICIPACIONES_REENVIAR,
    Permission.PARTICIPACIONES_REASIGNAR,
}

ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.MEMBER: _MEMBER_PERMISSIONS,
    UserRole.PARTICIPANT: _PARTICIPANT_PERMISSIONS,
    UserRole.ADMIN: _ADMIN_PERMISSIONS,
}


def has_permission(rol: UserRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(rol, frozenset())


def require_roles(*allowed_roles: UserRole):
    def dependency(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        if current_user.rol not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para realizar esta acción"
            )

        return current_user

    return dependency


def require_permission(permission: Permission):
    def dependency(
        current_user: UserModel = Depends(get_current_user)
    ) -> UserModel:
        if not has_permission(current_user.rol, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para realizar esta acción"
            )

        return current_user

    return dependency


def require_self_or_admin(
    user_id: UUID,
    current_user: UserModel = Depends(get_current_user)
) -> UserModel:
    if (
        current_user.rol != UserRole.ADMIN
        and current_user.id != user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para realizar esta acción"
        )

    return current_user
