from uuid import UUID

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from src.api.dependencies.auth import get_current_user
from src.core.constants.enums import UserRole
from src.infrastructure.database.models.user_model import UserModel


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
