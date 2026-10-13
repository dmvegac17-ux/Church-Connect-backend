from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from src.api.dependencies.schedules import get_schedule_service
from src.api.v1.schedules.schemas import CambioCronogramaResponse
from src.api.v1.schedules.schemas import CronogramaDeEvento
from src.api.v1.schedules.schemas import ScheduleCreate
from src.api.v1.schedules.schemas import ScheduleResponse
from src.api.v1.schedules.schemas import ScheduleTimesUpdate
from src.api.v1.schedules.schemas import ScheduleUpdate
from src.application.schedules.services import EventNotFoundError
from src.application.schedules.services import InvalidScheduleTimeError
from src.application.schedules.services import ScheduleNotFoundError
from src.application.schedules.services import ScheduleOutOfEventRangeError
from src.application.schedules.services import ScheduleOverlapError
from src.application.schedules.services import ScheduleService
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.security.permissions import require_roles
from src.infrastructure.database.models.user_model import UserModel


router = APIRouter(
    prefix="/schedules",
    tags=["Schedules"]
)


@router.get(
    "",
    response_model=ResponsePayload[list[ScheduleResponse]],
    summary="Listar cronogramas",
    description=(
        "Devuelve un listado paginado de cronogramas. Si se envía "
        "`evento_id`, devuelve únicamente los cronogramas de ese evento "
        "(sin paginar). Cualquier usuario autenticado puede consultarlos."
    ),
    responses={
        401: {"description": "No autenticado"},
    },
)
async def get_schedules(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    evento_id: UUID | None = Query(None),
    service: ScheduleService = Depends(
        get_schedule_service
    ),
    current_user: UserModel = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.MEMBER
        )
    )
):
    schedules = await service.get_all(
        limit=limit,
        offset=offset,
        evento_id=evento_id
    )

    total = await service.count(
        evento_id
    )

    # Un miembro no ve a quién se invitó hasta que esa persona confirma;
    # el administrador ve además en qué está cada responsable.
    if current_user.rol != UserRole.ADMIN:
        schedules = await service.para_miembro(schedules)
    else:
        schedules = await service.con_estado(schedules)

    return ResponsePayload.ok(
        data=schedules,
        message="Cronogramas obtenidos exitosamente",
        meta={"totalSchedules": total}
    )


# Va antes de `GET /{schedule_id}`: «agrupados» no es un id.
@router.get(
    "/agrupados",
    response_model=ResponsePayload[list[CronogramaDeEvento]],
    summary="Cronogramas agrupados por evento",
    description=(
        "Todos los eventos (también los que aún no tienen cronograma) con "
        "sus actividades ordenadas por hora y el estado de cada una: "
        "`confirmado`, `pendiente`, `por_reconfirmar`, `rechazado`, "
        "`sin_respuesta`, `sin_asignar` o `fuera_de_rango`. Solo el rol "
        "`admin`."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
    },
)
async def get_grouped_schedules(
    service: ScheduleService = Depends(
        get_schedule_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    return ResponsePayload.ok(
        data=await service.agrupados(),
        message="Cronogramas obtenidos exitosamente"
    )


# Va antes de `GET /{schedule_id}`: «historial» no es un id.
@router.get(
    "/historial",
    response_model=ResponsePayload[list[CambioCronogramaResponse]],
    summary="Historial de cambios del cronograma",
    description=(
        "Quién creó, editó o eliminó cada actividad del evento, cuándo, y "
        "qué valores tenía antes y después. Del más reciente al más antiguo. "
        "Solo el rol `admin`."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
    },
)
async def get_schedule_history(
    evento_id: UUID,
    service: ScheduleService = Depends(
        get_schedule_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    return ResponsePayload.ok(
        data=await service.historial(evento_id),
        message="Historial obtenido exitosamente"
    )


@router.get(
    "/{schedule_id}",
    response_model=ResponsePayload[ScheduleResponse],
    summary="Obtener cronograma por ID",
    description=(
        "Devuelve el detalle de un cronograma específico. "
        "Cualquier usuario autenticado puede consultar cronogramas."
    ),
    responses={
        401: {"description": "No autenticado"},
        404: {"description": "Cronograma no encontrado"},
    },
)
async def get_schedule(
    schedule_id: UUID,
    service: ScheduleService = Depends(
        get_schedule_service
    ),
    current_user: UserModel = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.MEMBER
        )
    )
):
    try:
        schedule = await service.get_by_id(
            schedule_id
        )

    except ScheduleNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    if current_user.rol != UserRole.ADMIN:
        schedule = (await service.para_miembro([schedule]))[0]

    return ResponsePayload.ok(
        data=schedule,
        message="Cronograma obtenido exitosamente"
    )


@router.post(
    "",
    response_model=ResponsePayload[ScheduleResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Crear cronograma",
    description=(
        "Registra un nuevo cronograma para un evento existente. "
        "Solo el rol `admin` puede crear cronogramas."
    ),
    responses={
        400: {
            "description": (
                "hora_fin debe ser posterior a hora_inicio, el horario "
                "está fuera del rango del evento, o se solapa con otra "
                "actividad del cronograma"
            )
        },
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Evento no encontrado"},
    },
)
async def create_schedule(
    request: ScheduleCreate,
    # Versión del evento que cargó el formulario: si ya no es la vigente,
    # otro administrador guardó antes y se responde 409.
    version: int | None = Query(None, ge=1),
    service: ScheduleService = Depends(
        get_schedule_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        schedule = await service.create(
            request,
            admin=current_user,
            version=version
        )

    except EventNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except (
        InvalidScheduleTimeError,
        ScheduleOutOfEventRangeError,
        ScheduleOverlapError
    ) as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=schedule,
        status_code=status.HTTP_201_CREATED,
        message="Cronograma creado exitosamente"
    )


# Va antes de `PUT /{schedule_id}`: «horarios» no es un id.
@router.put(
    "/horarios",
    response_model=ResponsePayload[list[ScheduleResponse]],
    summary="Cambiar el horario de varias actividades",
    description=(
        "Cambia de una vez el horario de varias actividades de un mismo "
        "evento (por ejemplo, al reordenar el cronograma e intercambiar sus "
        "horas). Se valida cómo queda el cronograma completo —dentro del "
        "horario del evento y sin solapamientos— y se guarda todo o nada. "
        "Devuelve todas las actividades del evento. Solo el rol `admin`."
    ),
    responses={
        400: {"description": "Horario inválido, fuera del evento o solapado"},
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Evento o actividad no encontrados"},
        409: {"description": "El evento ya finalizó"},
    },
)
async def reschedule(
    request: ScheduleTimesUpdate,
    # Versión del evento que cargó el formulario: si ya no es la vigente,
    # otro administrador guardó antes y se responde 409.
    version: int | None = Query(None, ge=1),
    service: ScheduleService = Depends(
        get_schedule_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        schedules = await service.reschedule(
            request,
            admin=current_user,
            version=version
        )

    except (EventNotFoundError, ScheduleNotFoundError) as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except (
        InvalidScheduleTimeError,
        ScheduleOutOfEventRangeError,
        ScheduleOverlapError
    ) as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=schedules,
        message="Horarios actualizados exitosamente"
    )


@router.put(
    "/{schedule_id}",
    response_model=ResponsePayload[ScheduleResponse],
    summary="Actualizar cronograma",
    description=(
        "Actualiza los datos de un cronograma existente. El `evento_id` no "
        "es modificable: si el cronograma pertenece a otro evento, debe "
        "eliminarse y crearse de nuevo. Solo el rol `admin` puede "
        "actualizar cronogramas."
    ),
    responses={
        400: {
            "description": (
                "Datos inválidos: hora_fin debe ser posterior a "
                "hora_inicio, el horario está fuera del rango del evento, "
                "o se solapa con otra actividad del cronograma"
            )
        },
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Cronograma no encontrado"},
    },
)
async def update_schedule(
    schedule_id: UUID,
    request: ScheduleUpdate,
    # Versión del evento que cargó el formulario: si ya no es la vigente,
    # otro administrador guardó antes y se responde 409.
    version: int | None = Query(None, ge=1),
    service: ScheduleService = Depends(
        get_schedule_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        schedule = await service.update(
            schedule_id=schedule_id,
            request=request,
            admin=current_user,
            version=version
        )

    except ScheduleNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except EventNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except (
        InvalidScheduleTimeError,
        ScheduleOutOfEventRangeError,
        ScheduleOverlapError
    ) as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=schedule,
        message="Cronograma actualizado exitosamente"
    )


@router.delete(
    "/{schedule_id}",
    response_model=ResponsePayload[None],
    summary="Eliminar cronograma",
    description=(
        "Elimina un cronograma existente. "
        "Solo el rol `admin` puede eliminar cronogramas."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Cronograma no encontrado"},
    },
)
async def delete_schedule(
    schedule_id: UUID,
    # Versión del evento que cargó el formulario: si ya no es la vigente,
    # otro administrador guardó antes y se responde 409.
    version: int | None = Query(None, ge=1),
    service: ScheduleService = Depends(
        get_schedule_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        await service.delete(
            schedule_id,
            admin=current_user,
            version=version
        )

    except ScheduleNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=None,
        message="Cronograma eliminado exitosamente"
    )
