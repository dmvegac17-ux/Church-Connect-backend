<<<<<<< Updated upstream
=======
from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from src.api.dependencies.schedules import get_schedule_service
from src.api.v1.schedules.schemas import ScheduleCreate
from src.api.v1.schedules.schemas import ScheduleResponse
from src.api.v1.schedules.schemas import ScheduleUpdate
from src.application.schedules.services import EventNotFoundError
from src.application.schedules.services import InvalidScheduleTimeError
from src.application.schedules.services import ScheduleNotFoundError
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
            UserRole.PARTICIPANT,
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

    return ResponsePayload.ok(
        data=schedules,
        message="Cronogramas obtenidos exitosamente",
        meta={"totalSchedules": total}
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
            UserRole.PARTICIPANT,
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
        400: {"description": "hora_fin debe ser posterior a hora_inicio"},
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Evento no encontrado"},
    },
)
async def create_schedule(
    request: ScheduleCreate,
    service: ScheduleService = Depends(
        get_schedule_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        schedule = await service.create(
            request
        )

    except EventNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except InvalidScheduleTimeError as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=schedule,
        status_code=status.HTTP_201_CREATED,
        message="Cronograma creado exitosamente"
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
        400: {"description": "Datos inválidos"},
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Cronograma no encontrado"},
    },
)
async def update_schedule(
    schedule_id: UUID,
    request: ScheduleUpdate,
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
            request=request
        )

    except ScheduleNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except InvalidScheduleTimeError as ex:
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
    service: ScheduleService = Depends(
        get_schedule_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        await service.delete(
            schedule_id
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
>>>>>>> Stashed changes
