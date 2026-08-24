from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from src.api.dependencies.notificaciones import get_notificacion_service
from src.api.v1.notificaciones.schemas import NotificationCreate
from src.api.v1.notificaciones.schemas import NotificationResponse
from src.api.v1.notificaciones.schemas import NotificationUpdate
from src.application.notificaciones.services import NotificacionesService
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.security.permissions import require_roles
from src.infrastructure.database.models.user_model import UserModel


router = APIRouter(
    prefix="/notificaciones",
    tags=["Notificaciones"]
)

@router.get(
    "",
    response_model=ResponsePayload[list[NotificationResponse]],
    summary="Listar notificaciones",
    description="Devuelve un listado paginado de notificaciones.",
    responses={
        401: {"description": "No autenticado"},
    },
)

async def get_notificaciones(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: NotificacionesService = Depends(
        get_notificacion_service
    ),
    current_user: UserModel = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.PARTICIPANT,
            UserRole.MEMBER
        )
    )
):
    notificaciones = await service.get_all(
        limit=limit,
        offset=offset
    )

    total = await service.count()

    return ResponsePayload.ok(
        data=notificaciones,
        message="Notificaciones obtenidas exitosamente",
        meta={"totalNotificaciones": total}
    )
@router.get(
    "/{notificacion_id}",
    response_model=ResponsePayload[NotificationResponse],
    summary="Obtener notificación por ID",
    responses={
        401: {"description": "No autenticado"},
        404: {"description": "Notificación no encontrada"},
    },
)
async def get_notificacion(
    notificacion_id: UUID,
    service: NotificacionesService = Depends(
        get_notificacion_service
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
        notificacion = await service.get_by_id(
            notificacion_id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=notificacion,
        message="Notificación obtenida exitosamente"
    )

@router.post(
    "",
    response_model=ResponsePayload[NotificationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Crear notificación",
)
async def create_notificacion(
    request: NotificationCreate,
    service: NotificacionesService = Depends(
        get_notificacion_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        notificacion = await service.create(
            request=request,
            user_id=current_user.id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=notificacion,
        status_code=status.HTTP_201_CREATED,
        message="Notificación creada exitosamente"
    )

@router.put(
    "/{notificacion_id}",
    response_model=ResponsePayload[NotificationResponse],
    summary="Actualizar notificación",
)
async def update_notificacion(
    notificacion_id: UUID,
    request: NotificationUpdate,
    service: NotificacionesService = Depends(
        get_notificacion_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        notificacion = await service.update(
            notificacion_id=notificacion_id,
            request=request
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=notificacion,
        message="Notificación actualizada exitosamente"
    )

@router.delete(
    "/{notificacion_id}",
    response_model=ResponsePayload[None],
    summary="Eliminar notificación",
)
async def delete_notificacion(
    notificacion_id: UUID,
    service: NotificacionesService = Depends(
        get_notificacion_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        await service.delete(
            notificacion_id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=None,
        message="Notificación eliminada exitosamente"
    )