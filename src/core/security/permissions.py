from enum import Enum
from uuid import UUID

from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi import status

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import get_current_user
from src.application.legal.services import LegalService
from src.core.constants.enums import UserRole
from src.infrastructure.database.models.user_model import UserModel
from src.infrastructure.database.session import get_db


class Permission(str, Enum):
    PARTICIPACIONES_VER_PROPIAS = "participaciones.ver_propias"
    PARTICIPACIONES_RESPONDER_PROPIAS = "participaciones.responder_propias"
    PARTICIPACIONES_SUPERVISAR = "participaciones.supervisar"
    PARTICIPACIONES_CANCELAR = "participaciones.cancelar"
    PARTICIPACIONES_REENVIAR = "participaciones.reenviar"
    PARTICIPACIONES_REASIGNAR = "participaciones.reasignar"


# Participar no es un rol: cualquier usuario activo puede ser asignado a una
# actividad, así que todos ven y responden sus propias invitaciones. Lo que
# protege cada invitación es su dueño (`participante_id`), no el rol.
_MEMBER_PERMISSIONS: frozenset[Permission] = frozenset({
    Permission.PARTICIPACIONES_VER_PROPIAS,
    Permission.PARTICIPACIONES_RESPONDER_PROPIAS,
})

# El administrador se compone a partir del miembro: también puede participar.
_ADMIN_PERMISSIONS: frozenset[Permission] = _MEMBER_PERMISSIONS | {
    Permission.PARTICIPACIONES_SUPERVISAR,
    Permission.PARTICIPACIONES_CANCELAR,
    Permission.PARTICIPACIONES_REENVIAR,
    Permission.PARTICIPACIONES_REASIGNAR,
}

ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.MEMBER: _MEMBER_PERMISSIONS,
    UserRole.ADMIN: _ADMIN_PERMISSIONS,
}


def has_permission(rol: UserRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(rol, frozenset())


ACEPTACION_PENDIENTE = "aceptacion_pendiente"


async def usuario_al_dia(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserModel:
    """
    El usuario autenticado, siempre que haya aceptado los documentos legales
    vigentes. Si tiene alguno pendiente, la API no le sirve nada más: `403`
    con `data.codigo = "aceptacion_pendiente"`.

    Quedan fuera las rutas que necesita para resolverlo, que dependen de
    `get_current_user` a secas (leer y aceptar los documentos, renovar la
    sesión) y la consulta de su propio usuario, con la que arranca la sesión.
    """
    es_su_usuario = request.method == "GET" and request.url.path.rstrip("/").endswith(
        f"/users/{current_user.id}"
    )

    if not es_su_usuario and await LegalService(db).pendientes(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": (
                    "Debes aceptar los términos y condiciones y la política "
                    "de privacidad vigentes para seguir usando la aplicación."
                ),
                "codigo": ACEPTACION_PENDIENTE,
            }
        )

    return current_user


def require_roles(*allowed_roles: UserRole):
    def dependency(
        current_user: UserModel = Depends(usuario_al_dia)
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
        current_user: UserModel = Depends(usuario_al_dia)
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
    current_user: UserModel = Depends(usuario_al_dia)
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
