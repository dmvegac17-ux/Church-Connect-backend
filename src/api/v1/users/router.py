from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from src.api.dependencies.users import get_user_service
from src.api.v1.users.schemas import UserCreate
from src.api.v1.users.schemas import UserResponse
from src.api.v1.users.schemas import UserUpdate
from src.application.users.services import UserHasRelatedRecordsError
from src.application.users.services import UserService
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.security.permissions import require_roles
from src.core.security.permissions import require_self_or_admin
from src.infrastructure.database.models.user_model import UserModel


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.get(
    "",
    response_model=ResponsePayload[list[UserResponse]],
    summary="Listar usuarios",
    description="Devuelve un listado paginado de usuarios. Solo el rol `admin` puede listar todos los usuarios.",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
    },
)
async def get_users(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: UserService = Depends(
        get_user_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    users = await service.get_all(
        limit=limit,
        offset=offset
    )
    total = await service.count()

    return ResponsePayload.ok(
        data=users,
        message="Usuarios obtenidos exitosamente",
        meta={"totalUsers": total}
    )


@router.get(
    "/{user_id}",
    response_model=ResponsePayload[UserResponse],
    summary="Obtener usuario por ID",
    description=(
        "Devuelve el detalle de un usuario específico. El rol `admin` puede "
        "consultar cualquier usuario; `participant` y `member` solo pueden "
        "consultar su propio perfil."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Usuario no encontrado"},
    },
)
async def get_user(
    user_id: UUID,
    service: UserService = Depends(
        get_user_service
    ),
    current_user: UserModel = Depends(
        require_self_or_admin
    )
):
    try:
        user = await service.get_by_id(
            user_id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=404,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=user,
        message="Usuario obtenido exitosamente"
    )


@router.post(
    "",
    response_model=ResponsePayload[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario",
    description="Registra un nuevo usuario en la plataforma. Solo el rol `admin` puede crear usuarios.",
    responses={
        400: {"description": "Datos inválidos o usuario ya existente"},
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
    },
)
async def create_user(
    request: UserCreate,
    service: UserService = Depends(
        get_user_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        user = await service.create(
            request
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=400,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=user,
        status_code=status.HTTP_201_CREATED,
        message="Usuario creado exitosamente"
    )


@router.put(
    "/{user_id}",
    response_model=ResponsePayload[UserResponse],
    summary="Actualizar usuario",
    description=(
        "Actualiza los datos de un usuario existente. El rol `admin` puede "
        "actualizar cualquier usuario, incluyendo `rol`, `activo` y "
        "`contrasena`; `participant` y `member` solo pueden actualizar su "
        "propio perfil, no pueden modificar `rol` ni `activo`, y solo "
        "pueden cambiar su propia `contrasena`."
    ),
    responses={
        400: {"description": "Datos inválidos"},
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
    },
)
async def update_user(
    user_id: UUID,
    request: UserUpdate,
    service: UserService = Depends(
        get_user_service
    ),
    current_user: UserModel = Depends(
        require_self_or_admin
    )
):
    if current_user.rol != UserRole.ADMIN:
        if request.rol is not None or request.activo is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para modificar el rol o el estado del usuario"
            )

    if request.contrasena is not None and current_user.id != user_id and current_user.rol != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para modificar la contraseña de otro usuario"
        )

    try:
        user = await service.update(
            user_id,
            request
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=400,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=user,
        message="Usuario actualizado exitosamente"
    )


@router.delete(
    "/{user_id}",
    response_model=ResponsePayload[None],
    summary="Eliminar usuario",
    description="Elimina un usuario existente. Solo el rol `admin` puede eliminar usuarios.",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Usuario no encontrado"},
        409: {"description": "El usuario tiene registros asociados"},
    },
)
async def delete_user(
    user_id: UUID,
    service: UserService = Depends(
        get_user_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        await service.delete(
            user_id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=404,
            detail=str(ex)
        )

    except UserHasRelatedRecordsError as ex:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=None,
        message="Usuario eliminado exitosamente"
    )