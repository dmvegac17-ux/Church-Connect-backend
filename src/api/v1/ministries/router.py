from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from src.api.dependencies.ministries import get_ministry_service
from src.api.v1.ministries.schemas import MinistryCreate
from src.api.v1.ministries.schemas import MinistryMemberResponse
from src.api.v1.ministries.schemas import MinistryResponse
from src.api.v1.ministries.schemas import MinistryUpdate
from src.application.ministries.services import DuplicateMembershipError
from src.application.ministries.services import MembershipNotFoundError
from src.application.ministries.services import MinistryNotFoundError
from src.application.ministries.services import MinistryService
from src.application.ministries.services import UserNotFoundError
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.security.permissions import require_roles
from src.infrastructure.database.models.user_model import UserModel


router = APIRouter(
    prefix="/ministries",
    tags=["Ministries"]
)


@router.get(
    "",
    response_model=ResponsePayload[list[MinistryResponse]],
    summary="Listar ministerios",
    description=(
        "Devuelve un listado paginado de ministerios. "
        "Cualquier usuario autenticado puede consultar los ministerios."
    ),
    responses={
        401: {"description": "No autenticado"},
    },
)
async def get_ministries(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: MinistryService = Depends(
        get_ministry_service
    ),
    current_user: UserModel = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.PARTICIPANT,
            UserRole.MEMBER
        )
    )
):
    ministries = await service.get_all(
        limit=limit,
        offset=offset
    )

    total = await service.count()

    return ResponsePayload.ok(
        data=ministries,
        message="Ministerios obtenidos exitosamente",
        meta={"totalMinistries": total}
    )


@router.get(
    "/{ministry_id}",
    response_model=ResponsePayload[MinistryResponse],
    summary="Obtener ministerio por ID",
    description=(
        "Devuelve el detalle de un ministerio específico. "
        "Cualquier usuario autenticado puede consultar ministerios."
    ),
    responses={
        401: {"description": "No autenticado"},
        404: {"description": "Ministerio no encontrado"},
    },
)
async def get_ministry(
    ministry_id: UUID,
    service: MinistryService = Depends(
        get_ministry_service
    ),
    current_user: UserModel = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.PARTICIPANT,
            UserRole.MEMBER
        )
    )
):
    try:
        ministry = await service.get_by_id(
            ministry_id
        )

    except MinistryNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=ministry,
        message="Ministerio obtenido exitosamente"
    )


@router.post(
    "",
    response_model=ResponsePayload[MinistryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Crear ministerio",
    description=(
        "Registra un nuevo ministerio en la plataforma. "
        "Solo el rol `admin` puede crear ministerios."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
    },
)
async def create_ministry(
    request: MinistryCreate,
    service: MinistryService = Depends(
        get_ministry_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    ministry = await service.create(
        request
    )

    return ResponsePayload.ok(
        data=ministry,
        status_code=status.HTTP_201_CREATED,
        message="Ministerio creado exitosamente"
    )


@router.put(
    "/{ministry_id}",
    response_model=ResponsePayload[MinistryResponse],
    summary="Actualizar ministerio",
    description=(
        "Actualiza los datos de un ministerio existente. "
        "Solo el rol `admin` puede actualizar ministerios."
    ),
    responses={
        400: {"description": "Datos inválidos"},
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Ministerio no encontrado"},
    },
)
async def update_ministry(
    ministry_id: UUID,
    request: MinistryUpdate,
    service: MinistryService = Depends(
        get_ministry_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        ministry = await service.update(
            ministry_id=ministry_id,
            request=request
        )

    except MinistryNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=ministry,
        message="Ministerio actualizado exitosamente"
    )


@router.delete(
    "/{ministry_id}",
    response_model=ResponsePayload[None],
    summary="Eliminar ministerio",
    description=(
        "Elimina un ministerio existente. Las membresías asociadas en "
        "`usuarios_ministry` no se eliminan: quedan con `ministerio_id` en "
        "NULL por la regla ON DELETE SET NULL definida en la base de datos. "
        "Solo el rol `admin` puede eliminar ministerios."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Ministerio no encontrado"},
    },
)
async def delete_ministry(
    ministry_id: UUID,
    service: MinistryService = Depends(
        get_ministry_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        await service.delete(
            ministry_id
        )

    except MinistryNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=None,
        message="Ministerio eliminado exitosamente"
    )


@router.get(
    "/{ministry_id}/users",
    response_model=ResponsePayload[list[MinistryMemberResponse]],
    summary="Listar usuarios de un ministerio",
    description=(
        "Devuelve un listado paginado de usuarios asignados a un ministerio. "
        "Cualquier usuario autenticado puede consultar esta lista."
    ),
    responses={
        401: {"description": "No autenticado"},
        404: {"description": "Ministerio no encontrado"},
    },
)
async def get_ministry_members(
    ministry_id: UUID,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: MinistryService = Depends(
        get_ministry_service
    ),
    current_user: UserModel = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.PARTICIPANT,
            UserRole.MEMBER
        )
    )
):
    try:
        members = await service.list_members(
            ministry_id=ministry_id,
            limit=limit,
            offset=offset
        )

    except MinistryNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    total = await service.count_members(
        ministry_id
    )

    return ResponsePayload.ok(
        data=members,
        message="Usuarios del ministerio obtenidos exitosamente",
        meta={"totalMembers": total}
    )


@router.post(
    "/{ministry_id}/users/{user_id}",
    response_model=ResponsePayload[None],
    status_code=status.HTTP_201_CREATED,
    summary="Asignar un usuario a un ministerio",
    description=(
        "Crea la relación entre un usuario y un ministerio. "
        "Solo el rol `admin` puede administrar esta relación."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Ministerio o usuario no encontrado"},
        409: {"description": "El usuario ya pertenece a este ministerio"},
    },
)
async def add_ministry_member(
    ministry_id: UUID,
    user_id: UUID,
    service: MinistryService = Depends(
        get_ministry_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        await service.add_member(
            ministry_id=ministry_id,
            user_id=user_id
        )

    except (MinistryNotFoundError, UserNotFoundError) as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except DuplicateMembershipError as ex:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=None,
        status_code=status.HTTP_201_CREATED,
        message="Usuario asignado al ministerio exitosamente"
    )


@router.delete(
    "/{ministry_id}/users/{user_id}",
    response_model=ResponsePayload[None],
    summary="Quitar un usuario de un ministerio",
    description=(
        "Elimina la relación entre un usuario y un ministerio. "
        "Solo el rol `admin` puede administrar esta relación."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Ministerio no encontrado o el usuario no pertenece a él"},
    },
)
async def remove_ministry_member(
    ministry_id: UUID,
    user_id: UUID,
    service: MinistryService = Depends(
        get_ministry_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        await service.remove_member(
            ministry_id=ministry_id,
            user_id=user_id
        )

    except (MinistryNotFoundError, MembershipNotFoundError) as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=None,
        message="Usuario removido del ministerio exitosamente"
    )
