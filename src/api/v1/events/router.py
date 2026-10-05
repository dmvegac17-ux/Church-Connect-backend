from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from src.api.dependencies.event import get_event_service
from src.api.v1.events.schemas import EventCreate
from src.api.v1.events.schemas import EventResponse
from src.api.v1.events.schemas import EventUpdate
from src.application.events.services import EventService
from src.application.events.services import InvalidEventDateRangeError
from src.application.events.services import InvalidEventLocationError
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.security.permissions import require_roles
from src.infrastructure.database.models.user_model import UserModel


router = APIRouter(
    prefix="/events",
    tags=["Events"]
)


@router.get(
    "",
    response_model=ResponsePayload[list[EventResponse]],
    summary="Listar eventos",
    description=(
        "Devuelve un listado paginado de eventos. "
        "Cualquier usuario autenticado puede consultar los eventos."
    ),
    responses={
        401: {"description": "No autenticado"},
    },
)
async def get_events(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: EventService = Depends(
        get_event_service
    ),
    current_user: UserModel = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.PARTICIPANT,
            UserRole.MEMBER
        )
    )
):
    events = await service.get_all(
        limit=limit,
        offset=offset
    )

    total = await service.count()

    return ResponsePayload.ok(
        data=events,
        message="Eventos obtenidos exitosamente",
        meta={"totalEvents": total}
    )


@router.get(
    "/{event_id}",
    response_model=ResponsePayload[EventResponse],
    summary="Obtener evento por ID",
    description=(
        "Devuelve el detalle de un evento específico. "
        "Cualquier usuario autenticado puede consultar eventos."
    ),
    responses={
        401: {"description": "No autenticado"},
        404: {"description": "Evento no encontrado"},
    },
)
async def get_event(
    event_id: UUID,
    service: EventService = Depends(
        get_event_service
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
        event = await service.get_by_id(
            event_id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=event,
        message="Evento obtenido exitosamente"
    )


@router.post(
    "",
    response_model=ResponsePayload[EventResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Crear evento",
    description=(
        "Registra un nuevo evento en la plataforma. "
        "Solo el rol `admin` puede crear eventos."
    ),
    responses={
        400: {
            "description": (
                "La fecha/hora de fin debe ser posterior a la de inicio, "
                "o latitud/longitud se enviaron incompletas"
            )
        },
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
    },
)
async def create_event(
    request: EventCreate,
    service: EventService = Depends(
        get_event_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        event = await service.create(
            request=request,
            user_id=current_user.id
        )

    except (
        InvalidEventDateRangeError,
        InvalidEventLocationError
    ) as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ex)
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=event,
        status_code=status.HTTP_201_CREATED,
        message="Evento creado exitosamente"
    )


@router.put(
    "/{event_id}",
    response_model=ResponsePayload[EventResponse],
    summary="Actualizar evento",
    description=(
        "Actualiza los datos de un evento existente. "
        "Solo el rol `admin` puede actualizar eventos."
    ),
    responses={
        400: {"description": "Datos inválidos"},
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Evento no encontrado"},
    },
)
async def update_event(
    event_id: UUID,
    request: EventUpdate,
    service: EventService = Depends(
        get_event_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        event = await service.update(
            event_id=event_id,
            request=request
        )

    except (
        InvalidEventDateRangeError,
        InvalidEventLocationError
    ) as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ex)
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=event,
        message="Evento actualizado exitosamente"
    )


@router.delete(
    "/{event_id}",
    response_model=ResponsePayload[None],
    summary="Eliminar evento",
    description=(
        "Elimina un evento existente y, en cascada, sus cronogramas, "
        "asistencias, inscripciones y confirmaciones por correo asociadas. "
        "Solo el rol `admin` puede eliminar eventos."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Evento no encontrado"},
    },
)
async def delete_event(
    event_id: UUID,
    service: EventService = Depends(
        get_event_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        await service.delete(
            event_id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=None,
        message="Evento eliminado exitosamente"
    )