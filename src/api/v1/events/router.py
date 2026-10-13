from uuid import UUID

from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from src.api.dependencies.event import get_event_service
from src.api.dependencies.participaciones import get_email_service
from src.api.v1.events.schemas import EventCreate
from src.api.v1.events.schemas import EventResponse
from src.api.v1.events.schemas import EventUpdate
from src.application.events.date_change import EventChangeEmail
from src.application.events.services import EventCapacityBelowOccupiedError
from src.application.events.services import EventService
from src.application.events.services import InvalidEventDateRangeError
from src.application.events.services import InvalidEventLocationError
from src.application.events.services import InvalidRegistrationDeadlineError
from src.application.schedules.services import ActividadesFueraDeRangoError
from src.application.schedules.services import InvalidScheduleTimeError
from src.application.schedules.services import ScheduleNotFoundError
from src.application.schedules.services import ScheduleOverlapError
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.security.permissions import require_roles
from src.core.logging.logger import logger
from src.infrastructure.database.models.user_model import UserModel
from src.infrastructure.email.email_service import EmailService


router = APIRouter(
    prefix="/events",
    tags=["Events"]
)


async def _enviar_avisos(
    mailer: EmailService,
    correos: list[EventChangeEmail]
) -> None:
    """
    Corre después de responder: avisar a muchos inscritos no debe hacer
    esperar a quien guarda el evento. Un correo que falla no detiene los demás.
    """
    for correo in correos:
        try:
            await mailer.send_notification(
                to=correo.to,
                titulo=correo.titulo,
                mensaje=correo.mensaje,
                usuario_nombre=correo.usuario_nombre
            )
        except Exception:
            logger.exception(
                "Fallo al avisar el cambio del evento a %s",
                correo.to
            )


@router.get(
    "",
    response_model=ResponsePayload[list[EventResponse]],
    summary="Listar eventos",
    description=(
        "Devuelve un listado paginado de eventos con su `aforo`. "
        "Cualquier usuario autenticado puede consultar los eventos. El "
        "administrador recibe el aforo total, los participantes y el público "
        "inscrito; el miembro solo su cupo (`capacidad` = aforo menos "
        "participantes) y los disponibles."
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
            UserRole.MEMBER
        )
    )
):
    events = await service.get_all(
        limit=limit,
        offset=offset,
        user=current_user
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
            UserRole.MEMBER
        )
    )
):
    try:
        event = await service.get_by_id(
            event_id,
            current_user
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
            user=current_user
        )

    except (
        InvalidEventDateRangeError,
        InvalidEventLocationError,
        InvalidRegistrationDeadlineError
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
        "Solo el rol `admin` puede actualizar eventos. Un evento que ya "
        "finalizó no se puede editar (solo eliminar). Si cambia la fecha, "
        "el horario, el lugar o la dirección y hay personas inscritas, se les "
        "avisa por correo y en su bandeja con el valor anterior y el nuevo. "
        "No avisan los demás campos ni los retoques de texto (mayúsculas, "
        "tildes o una errata corregida). `meta.inscritosNotificados` indica "
        "a cuántas personas se avisó."
    ),
    responses={
        400: {"description": "Datos inválidos"},
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Evento no encontrado"},
        409: {
            "description": (
                "El evento ya finalizó (`data.codigo = evento_finalizado`) o "
                "el aforo es menor que los lugares ocupados"
            )
        },
    },
)
async def update_event(
    event_id: UUID,
    request: EventUpdate,
    background: BackgroundTasks,
    service: EventService = Depends(
        get_event_service
    ),
    mailer: EmailService = Depends(
        get_email_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        event, correos = await service.update(
            event_id=event_id,
            request=request,
            user=current_user
        )

    except EventCapacityBelowOccupiedError as ex:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(ex),
                "campo": "capacidad",
                "ocupados": ex.ocupados,
            }
        )

    except ActividadesFueraDeRangoError as ex:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(ex),
                "codigo": ex.codigo,
                "actividades": ex.actividades,
            }
        )

    except (
        InvalidScheduleTimeError,
        ScheduleOverlapError,
        ScheduleNotFoundError
    ) as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ex)
        )

    except (
        InvalidEventDateRangeError,
        InvalidEventLocationError,
        InvalidRegistrationDeadlineError
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

    if correos:
        background.add_task(_enviar_avisos, mailer, correos)

    return ResponsePayload.ok(
        data=event,
        message="Evento actualizado exitosamente",
        meta={"inscritosNotificados": len(correos)}
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