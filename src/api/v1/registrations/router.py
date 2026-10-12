from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from src.api.dependencies.registrations import get_registration_service
from src.api.v1.registrations.schemas import RegistrationCreate
from src.api.v1.registrations.schemas import RegistrationResponse
from src.api.v1.registrations.schemas import RegistrationUpdate
from src.application.registrations.services import EventNotFoundError
from src.application.registrations.services import ForbiddenRegistrationAccessError
from src.application.registrations.services import RegistrationConflictError
from src.application.registrations.services import RegistrationNotFoundError
from src.application.registrations.services import RegistrationService
from src.application.registrations.services import UserNotFoundError
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.security.permissions import require_roles
from src.infrastructure.database.models.user_model import UserModel


router = APIRouter(
    prefix="/registrations",
    tags=["Registrations"]
)


def _conflicto(ex: RegistrationConflictError) -> HTTPException:
    # `codigo` viaja en `data` para que el cliente distinga el motivo:
    # sin_cupos, ya_inscrito, es_participante, inscripciones_cerradas o
    # cancelacion_cerrada.
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"message": str(ex), "codigo": ex.codigo}
    )


@router.get(
    "",
    response_model=ResponsePayload[list[RegistrationResponse]],
    summary="Listar todas las inscripciones",
    description=(
        "Devuelve un listado paginado de todas las inscripciones de la "
        "plataforma. Si se envía `evento_id`, filtra por ese evento. "
        "Solo el rol `admin` puede consultar inscripciones de otros "
        "usuarios; para las propias, usar `GET /registrations/me`."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
    },
)
async def get_registrations(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    evento_id: UUID | None = Query(None),
    service: RegistrationService = Depends(
        get_registration_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    registrations = await service.get_all(
        limit=limit,
        offset=offset,
        evento_id=evento_id
    )

    total = await service.count(
        evento_id
    )

    return ResponsePayload.ok(
        data=registrations,
        message="Inscripciones obtenidas exitosamente",
        meta={"totalRegistrations": total}
    )


@router.get(
    "/me",
    response_model=ResponsePayload[list[RegistrationResponse]],
    summary="Listar mis inscripciones",
    description=(
        "Devuelve un listado paginado de las inscripciones del usuario "
        "autenticado."
    ),
    responses={
        401: {"description": "No autenticado"},
    },
)
async def get_my_registrations(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: RegistrationService = Depends(
        get_registration_service
    ),
    current_user: UserModel = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.MEMBER
        )
    )
):
    registrations = await service.get_my_registrations(
        user_id=current_user.id,
        limit=limit,
        offset=offset
    )

    total = await service.count_my_registrations(
        current_user.id
    )

    return ResponsePayload.ok(
        data=registrations,
        message="Inscripciones obtenidas exitosamente",
        meta={"totalRegistrations": total}
    )


@router.get(
    "/{registration_id}",
    response_model=ResponsePayload[RegistrationResponse],
    summary="Obtener inscripción por ID",
    description=(
        "Devuelve el detalle de una inscripción específica. Solo el "
        "dueño de la inscripción o un `admin` pueden consultarla."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Inscripción no encontrada"},
    },
)
async def get_registration(
    registration_id: UUID,
    service: RegistrationService = Depends(
        get_registration_service
    ),
    current_user: UserModel = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.MEMBER
        )
    )
):
    try:
        registration = await service.get_by_id(
            registration_id,
            current_user
        )

    except RegistrationNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except ForbiddenRegistrationAccessError as ex:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=registration,
        message="Inscripción obtenida exitosamente"
    )


@router.post(
    "",
    response_model=ResponsePayload[RegistrationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Inscribirse a un evento",
    description=(
        "Inscribe al usuario autenticado como público de un evento. Un "
        "`admin` puede enviar `usuario_id` para inscribir a otra persona y "
        "una `nota`. El cupo se valida de forma atómica contra el aforo "
        "menos los participantes. Quien participa en el evento no se "
        "inscribe: ya ocupa su lugar."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Solo un administrador inscribe a otra persona"},
        404: {"description": "Evento o usuario no encontrado"},
        409: {
            "description": (
                "No procede; `data.codigo` indica el motivo: `sin_cupos`, "
                "`ya_inscrito`, `es_participante` o `inscripciones_cerradas`"
            )
        },
    },
)
async def create_registration(
    request: RegistrationCreate,
    service: RegistrationService = Depends(
        get_registration_service
    ),
    current_user: UserModel = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.MEMBER
        )
    )
):
    try:
        registration = await service.create(
            evento_id=request.evento_id,
            current_user=current_user,
            usuario_id=request.usuario_id,
            nota=request.nota
        )

    except (EventNotFoundError, UserNotFoundError) as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except ForbiddenRegistrationAccessError as ex:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(ex)
        )

    except RegistrationConflictError as ex:
        raise _conflicto(ex)

    return ResponsePayload.ok(
        data=registration,
        status_code=status.HTTP_201_CREATED,
        message="Inscripción realizada exitosamente"
    )


@router.patch(
    "/{registration_id}",
    response_model=ResponsePayload[RegistrationResponse],
    summary="Editar la nota de una inscripción",
    description="Solo el rol `admin` puede editar la nota de una inscripción.",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Inscripción no encontrada"},
    },
)
async def update_registration(
    registration_id: UUID,
    request: RegistrationUpdate,
    service: RegistrationService = Depends(
        get_registration_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        registration = await service.update_note(
            registration_id,
            request.nota
        )

    except RegistrationNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=registration,
        message="Inscripción actualizada exitosamente"
    )


@router.delete(
    "/{registration_id}",
    response_model=ResponsePayload[None],
    summary="Cancelar inscripción",
    description=(
        "Cancela una inscripción existente. Solo el dueño de la "
        "inscripción o un `admin` pueden cancelarla."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Inscripción no encontrada"},
        409: {
            "description": (
                "`cancelacion_cerrada`: el evento ya empezó o pasó el límite "
                "de días para cancelar (solo aplica al dueño; un `admin` "
                "siempre puede)"
            )
        },
    },
)
async def delete_registration(
    registration_id: UUID,
    service: RegistrationService = Depends(
        get_registration_service
    ),
    current_user: UserModel = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.MEMBER
        )
    )
):
    try:
        await service.delete(
            registration_id,
            current_user
        )

    except RegistrationNotFoundError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    except ForbiddenRegistrationAccessError as ex:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(ex)
        )

    except RegistrationConflictError as ex:
        raise _conflicto(ex)

    return ResponsePayload.ok(
        data=None,
        message="Inscripción cancelada exitosamente"
    )
