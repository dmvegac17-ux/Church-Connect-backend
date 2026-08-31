from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from src.api.dependencies.confirmaciones_email import get_confirmacion_email_service
from src.api.v1.confirmaciones_email.schemas import ConfirmacionEmailCreate
from src.api.v1.confirmaciones_email.schemas import ConfirmacionEmailResponse
from src.api.v1.confirmaciones_email.schemas import ConfirmacionEmailUpdate
from src.application.confirmaciones_email.services import ConfirmacionEmailNotFoundError
from src.application.confirmaciones_email.services import ConfirmacionEmailService
from src.application.confirmaciones_email.services import EventNotFoundError
from src.application.confirmaciones_email.services import ForbiddenConfirmacionAccessError
from src.core.constants.enums import EstadoConfirmacion
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.security.permissions import require_roles
from src.infrastructure.database.models.user_model import UserModel


router = APIRouter(
    prefix="/confirmaciones",
    tags=["Confirmaciones"]
)


@router.get(
    "",
    response_model=ResponsePayload[list[ConfirmacionEmailResponse]],
    summary="Listar confirmaciones de email",
    description=(
        "Devuelve un listado paginado de confirmaciones, ordenado por "
        "`fecha_envio` descendente. Los roles `participant`/`member` solo "
        "ven sus propias confirmaciones (el filtro `usuario_id` se ignora "
        "para ellos); solo `admin` puede consultar o filtrar las de "
        "cualquier usuario."
    ),
    responses={
        401: {"description": "No autenticado"},
    },
)
async def get_confirmaciones(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    usuario_id: UUID | None = Query(None),
    evento_id: UUID | None = Query(None),
    estado: EstadoConfirmacion | None = Query(None),
    service: ConfirmacionEmailService = Depends(
        get_confirmacion_email_service
    ),
    current_user: UserModel = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.PARTICIPANT,
            UserRole.MEMBER
        )
    )
):
    confirmaciones = await service.get_all(
        current_user=current_user,
        limit=limit,
        offset=offset,
        usuario_id=usuario_id,
        evento_id=evento_id,
        estado=estado
    )

    total = await service.count(
        current_user=current_user,
        usuario_id=usuario_id,
        evento_id=evento_id,
        estado=estado
    )

    return ResponsePayload.ok(
        data=confirmaciones,
        message="Confirmaciones obtenidas exitosamente",
        meta={"totalConfirmaciones": total}
    )


@router.get(
    "/{confirmacion_id}",
    response_model=ResponsePayload[ConfirmacionEmailResponse],
    summary="Obtener confirmación por ID",
    description=(
        "Devuelve el detalle de una confirmación específica. Solo el "
        "dueño de la confirmación o un `admin` pueden consultarla."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Confirmación no encontrada"},
    },
)
async def get_confirmacion(
    confirmacion_id: UUID,
    service: ConfirmacionEmailService = Depends(
        get_confirmacion_email_service
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
        confirmacion = await service.get_by_id(
            confirmacion_id,
            current_user
        )

    except ConfirmacionEmailNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except ForbiddenConfirmacionAccessError as ex:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=confirmacion,
        message="Confirmación obtenida exitosamente"
    )


@router.post(
    "",
    response_model=ResponsePayload[ConfirmacionEmailResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Registrar confirmación de email",
    description=(
        "Registra una confirmación de asistencia enviada para un evento. "
        "El `usuario_id` siempre se toma del token, nunca del cuerpo de "
        "la solicitud. Cualquier usuario autenticado puede registrar sus "
        "propias confirmaciones."
    ),
    responses={
        401: {"description": "No autenticado"},
        404: {"description": "Evento no encontrado"},
        422: {"description": "Datos inválidos"},
    },
)
async def create_confirmacion(
    request: ConfirmacionEmailCreate,
    service: ConfirmacionEmailService = Depends(
        get_confirmacion_email_service
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
        confirmacion = await service.create(
            request,
            current_user
        )

    except EventNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=confirmacion,
        status_code=status.HTTP_201_CREATED,
        message="Confirmación registrada exitosamente"
    )


@router.put(
    "/{confirmacion_id}",
    response_model=ResponsePayload[ConfirmacionEmailResponse],
    summary="Actualizar confirmación de email",
    description=(
        "Actualiza `telefono`, `mensaje` y/o `estado` de una confirmación "
        "existente. `usuario_id`, `evento_id` y `fecha_envio` no son "
        "modificables. Solo el dueño de la confirmación o un `admin` "
        "pueden actualizarla."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Confirmación no encontrada"},
        422: {"description": "Datos inválidos"},
    },
)
async def update_confirmacion(
    confirmacion_id: UUID,
    request: ConfirmacionEmailUpdate,
    service: ConfirmacionEmailService = Depends(
        get_confirmacion_email_service
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
        confirmacion = await service.update(
            confirmacion_id,
            request,
            current_user
        )

    except ConfirmacionEmailNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except ForbiddenConfirmacionAccessError as ex:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=confirmacion,
        message="Confirmación actualizada exitosamente"
    )


@router.delete(
    "/{confirmacion_id}",
    response_model=ResponsePayload[None],
    summary="Eliminar confirmación de email",
    description=(
        "Elimina una confirmación existente. Solo el dueño de la "
        "confirmación o un `admin` pueden eliminarla."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Confirmación no encontrada"},
    },
)
async def delete_confirmacion(
    confirmacion_id: UUID,
    service: ConfirmacionEmailService = Depends(
        get_confirmacion_email_service
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
        await service.delete(
            confirmacion_id,
            current_user
        )

    except ConfirmacionEmailNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except ForbiddenConfirmacionAccessError as ex:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=None,
        message="Confirmación eliminada exitosamente"
    )
