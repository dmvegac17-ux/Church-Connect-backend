from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Response
from fastapi import status

from src.api.dependencies.notificaciones import get_notificacion_service
from src.api.v1.notificaciones.schemas import NotificationBulkCreate
from src.api.v1.notificaciones.schemas import NotificationCreate
from src.api.v1.notificaciones.schemas import NotificationResponse
from src.api.v1.notificaciones.schemas import NotificationUpdate
from src.application.notificaciones.services import NotificacionesService
from src.application.notificaciones.services import UserNotFoundError
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.schemas.response import status_name
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
    description=(
        "Devuelve un listado paginado de las notificaciones del usuario "
        "autenticado. Nadie puede ver notificaciones de otro usuario, "
        "sin importar su rol (ni siquiera `admin`)."
    ),
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
    usuario_id = current_user.id

    notificaciones = await service.get_all(
        limit=limit,
        offset=offset,
        usuario_id=usuario_id
    )

    total = await service.count(
        usuario_id
    )

    return ResponsePayload.ok(
        data=notificaciones,
        message="Notificaciones obtenidas exitosamente",
        meta={"totalNotificaciones": total}
    )
@router.get(
    "/{notificacion_id}",
    response_model=ResponsePayload[NotificationResponse],
    summary="Obtener notificación por ID",
    description=(
        "Devuelve el detalle de una notificación específica. Solo puede "
        "consultarla el usuario al que va dirigida; nadie más, sin importar "
        "su rol (ni siquiera `admin`)."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para ver esta notificación"},
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

    if notificacion.usuario_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para ver esta notificación"
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
    description=(
        "Registra una nueva notificación para un usuario existente y le "
        "envía un correo con el título y el mensaje (best-effort: si el "
        "envío falla o no hay SMTP configurado, la notificación igual se "
        "crea). Solo el rol `admin` puede crear notificaciones."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Usuario no encontrado"},
    },
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
            remitente=current_user
        )

    except UserNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=notificacion,
        status_code=status.HTTP_201_CREATED,
        message="Notificación creada exitosamente"
    )

@router.post(
    "/masivo",
    response_model=ResponsePayload[list[NotificationResponse]],
    status_code=status.HTTP_201_CREATED,
    summary="Enviar notificaciones masivas",
    description=(
        "Registra y envía la misma notificación (título y mensaje) a una "
        "lista de usuarios. Cada usuario se procesa de forma independiente: "
        "si uno falla (usuario inexistente, error de base de datos), no "
        "afecta a los demás. Solo el rol `admin` puede usar este endpoint."
    ),
    responses={
        207: {"description": "Envío parcial: algunas notificaciones fallaron"},
        400: {"description": "usuarios_ids es requerido y no puede estar vacío"},
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        500: {"description": "Ninguna notificación pudo procesarse"},
    },
)
async def create_notificaciones_masivas(
    request: NotificationBulkCreate,
    response: Response,
    service: NotificacionesService = Depends(
        get_notificacion_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    if not request.usuarios_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe indicar al menos un usuario en usuarios_ids"
        )

    creadas, errores = await service.create_bulk(
        request,
        remitente=current_user
    )

    total = len(request.usuarios_ids)
    exitosas = len(creadas)
    fallidas = len(errores)

    meta = {
        "total": total,
        "exitosas": exitosas,
        "fallidas": fallidas
    }

    if exitosas == 0:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        return ResponsePayload(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            status=status_name(status.HTTP_500_INTERNAL_SERVER_ERROR),
            data=None,
            success=False,
            message="No se pudo enviar ninguna notificación",
            errors=errores,
            meta=meta
        )

    if fallidas > 0:
        response.status_code = status.HTTP_207_MULTI_STATUS

        return ResponsePayload(
            status_code=status.HTTP_207_MULTI_STATUS,
            status=status_name(status.HTTP_207_MULTI_STATUS),
            data=creadas,
            success=True,
            message=(
                f"Se enviaron {exitosas} notificaciones exitosamente "
                f"y {fallidas} fallaron"
            ),
            errors=errores,
            meta=meta
        )

    return ResponsePayload.ok(
        data=creadas,
        status_code=status.HTTP_201_CREATED,
        message=f"Se enviaron {exitosas} notificaciones exitosamente",
        meta=meta
    )

@router.put(
    "/{notificacion_id}",
    response_model=ResponsePayload[NotificationResponse],
    summary="Actualizar notificación",
    description=(
        "Actualiza los datos de una notificación existente (título, "
        "mensaje o el estado `leida`). El `usuario_id` no es modificable. "
        "El rol `admin` puede actualizar cualquier notificación por "
        "completo; el usuario dueño de la notificación solo puede marcarla "
        "como `leida`, sin modificar `titulo` ni `mensaje`."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Notificación no encontrada"},
    },
)
async def update_notificacion(
    notificacion_id: UUID,
    request: NotificationUpdate,
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
        notificacion_actual = await service.get_by_id(
            notificacion_id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    if current_user.rol != UserRole.ADMIN:
        if notificacion_actual.usuario_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para modificar esta notificación"
            )

        if request.titulo is not None or request.mensaje is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo puede marcar la notificación como leída"
            )

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
    description=(
        "Elimina una notificación existente. "
        "Solo el rol `admin` puede eliminar notificaciones."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Notificación no encontrada"},
    },
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