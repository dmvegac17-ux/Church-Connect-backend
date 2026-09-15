from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from src.api.dependencies.attendances import get_attendance_service
from src.api.v1.attendances.schemas import AttendanceCreate
from src.api.v1.attendances.schemas import AttendanceResponse
from src.api.v1.attendances.schemas import AttendanceUpdate
from src.application.attendances.services import AttendanceNotFoundError
from src.application.attendances.services import AttendanceService
from src.application.attendances.services import AttendanceUserNotFoundError
from src.application.attendances.services import DuplicateAttendanceError
from src.application.attendances.services import EventNotFoundError
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.security.permissions import require_roles
from src.infrastructure.database.models.user_model import UserModel


router = APIRouter(
    prefix="/attendances",
    tags=["Attendances"]
)


@router.get(
    "",
    response_model=ResponsePayload[list[AttendanceResponse]],
    summary="Listar asistencias",
    description=(
        "Devuelve un listado paginado de asistencias. Si se envían "
        "`usuario_id` y/o `evento_id`, filtra por esos valores. "
        "Solo el rol `admin` puede consultar asistencias."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
    },
)
async def get_attendances(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    usuario_id: UUID | None = Query(None),
    evento_id: UUID | None = Query(None),
    service: AttendanceService = Depends(
        get_attendance_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    attendances = await service.get_all(
        limit=limit,
        offset=offset,
        usuario_id=usuario_id,
        evento_id=evento_id
    )

    total = await service.count(
        usuario_id=usuario_id,
        evento_id=evento_id
    )

    return ResponsePayload.ok(
        data=attendances,
        message="Asistencias obtenidas exitosamente",
        meta={"totalAttendances": total}
    )


@router.get(
    "/{attendance_id}",
    response_model=ResponsePayload[AttendanceResponse],
    summary="Obtener asistencia por ID",
    description=(
        "Devuelve el detalle de una asistencia específica. "
        "Solo el rol `admin` puede consultar asistencias."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Asistencia no encontrada"},
    },
)
async def get_attendance(
    attendance_id: UUID,
    service: AttendanceService = Depends(
        get_attendance_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        attendance = await service.get_by_id(
            attendance_id
        )

    except AttendanceNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=attendance,
        message="Asistencia obtenida exitosamente"
    )


@router.post(
    "",
    response_model=ResponsePayload[AttendanceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Registrar asistencia",
    description=(
        "Registra la asistencia de un usuario a un evento. "
        "`publicado_por` siempre se toma del token, nunca del cuerpo de "
        "la solicitud. Solo el rol `admin` puede registrar asistencias."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Usuario o evento no encontrado"},
        409: {"description": "Ya existe una asistencia para ese usuario y evento"},
    },
)
async def create_attendance(
    request: AttendanceCreate,
    service: AttendanceService = Depends(
        get_attendance_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        attendance = await service.create(
            request,
            current_user
        )

    except (AttendanceUserNotFoundError, EventNotFoundError) as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except DuplicateAttendanceError as ex:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=attendance,
        status_code=status.HTTP_201_CREATED,
        message="Asistencia registrada exitosamente"
    )


@router.put(
    "/{attendance_id}",
    response_model=ResponsePayload[AttendanceResponse],
    summary="Actualizar asistencia",
    description=(
        "Actualiza los datos de una asistencia existente. "
        "Solo el rol `admin` puede actualizar asistencias."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Asistencia, usuario o evento no encontrado"},
        409: {"description": "Ya existe una asistencia para ese usuario y evento"},
    },
)
async def update_attendance(
    attendance_id: UUID,
    request: AttendanceUpdate,
    service: AttendanceService = Depends(
        get_attendance_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        attendance = await service.update(
            attendance_id=attendance_id,
            request=request
        )

    except AttendanceNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except (AttendanceUserNotFoundError, EventNotFoundError) as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except DuplicateAttendanceError as ex:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=attendance,
        message="Asistencia actualizada exitosamente"
    )


@router.delete(
    "/{attendance_id}",
    response_model=ResponsePayload[None],
    summary="Eliminar asistencia",
    description=(
        "Elimina una asistencia existente. "
        "Solo el rol `admin` puede eliminar asistencias."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Asistencia no encontrada"},
    },
)
async def delete_attendance(
    attendance_id: UUID,
    service: AttendanceService = Depends(
        get_attendance_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        await service.delete(
            attendance_id
        )

    except AttendanceNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=None,
        message="Asistencia eliminada exitosamente"
    )
