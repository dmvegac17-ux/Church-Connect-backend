from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from src.api.dependencies.participaciones import get_participacion_service
from src.api.v1.participaciones.schemas import DatosReasignacion
from src.api.v1.participaciones.schemas import InvitacionCreate
from src.api.v1.participaciones.schemas import InvitacionesPropias
from src.api.v1.participaciones.schemas import InvitacionPropia
from src.api.v1.participaciones.schemas import ParticipacionAdmin
from src.api.v1.participaciones.schemas import ParticipacionesAdmin
from src.api.v1.participaciones.schemas import ParticipanteElegible
from src.api.v1.participaciones.schemas import RechazoRequest
from src.api.v1.participaciones.schemas import ReemplazoRequest
from src.api.v1.participaciones.schemas import ReemplazoResultado
from src.application.participaciones.services import ActividadNoEncontradaError
from src.application.participaciones.services import EstadoInvitacionError
from src.application.participaciones.services import InvitacionNoEncontradaError
from src.application.participaciones.services import ParticipacionService
from src.application.participaciones.services import ParticipanteInvalidoError
from src.application.participaciones.services import PlazoInvalidoError
from src.core.schemas.response import ResponsePayload
from src.core.security.permissions import Permission
from src.core.security.permissions import require_permission
from src.infrastructure.database.models.user_model import UserModel


router = APIRouter(tags=["Participaciones"])

_RESPUESTAS_COMUNES = {
    401: {"description": "No autenticado"},
    403: {"description": "No tiene permisos para realizar esta acción"},
}


def _traducir(ex: Exception) -> HTTPException:
    """Errores del servicio → respuesta HTTP con los datos que usa el cliente."""
    if isinstance(ex, (InvitacionNoEncontradaError, ActividadNoEncontradaError)):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    if isinstance(ex, EstadoInvitacionError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(ex), "estado_actual": ex.estado_actual}
        )

    if isinstance(ex, PlazoInvalidoError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": str(ex),
                "campo": "dias_para_confirmar",
                "dias_hasta_evento": ex.dias_hasta_evento,
                "dias_para_confirmar_max": ex.dias_para_confirmar_max,
            }
        )

    if isinstance(ex, ParticipanteInvalidoError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(ex), "campo": "participante_id"}
        )

    raise ex


_ERRORES = (
    InvitacionNoEncontradaError,
    ActividadNoEncontradaError,
    EstadoInvitacionError,
    PlazoInvalidoError,
    ParticipanteInvalidoError,
)


# ── Participante: solo sus propias invitaciones ─────────────────────────

@router.get(
    "/participante/invitaciones",
    response_model=ResponsePayload[InvitacionesPropias],
    summary="Listar mis invitaciones",
    description=(
        "Invitaciones del usuario autenticado. `pendientes` son las que "
        "esperan respuesta; `respondidas`, todas las demás."
    ),
    responses=_RESPUESTAS_COMUNES,
)
async def listar_mis_invitaciones(
    vista: Literal["pendientes", "respondidas", "todas"] = Query("pendientes"),
    service: ParticipacionService = Depends(get_participacion_service),
    current_user: UserModel = Depends(
        require_permission(Permission.PARTICIPACIONES_VER_PROPIAS)
    )
):
    data = await service.listar_propias(current_user, vista)

    return ResponsePayload.ok(
        data=data,
        message="Invitaciones obtenidas exitosamente"
    )


@router.post(
    "/participante/invitaciones/{invitacion_id}/aceptar",
    response_model=ResponsePayload[InvitacionPropia],
    summary="Aceptar una invitación",
    responses={
        **_RESPUESTAS_COMUNES,
        404: {"description": "La invitación no existe o no es del usuario"},
        409: {"description": "Ya fue respondida, venció o fue cancelada"},
    },
)
async def aceptar_invitacion(
    invitacion_id: UUID,
    service: ParticipacionService = Depends(get_participacion_service),
    current_user: UserModel = Depends(
        require_permission(Permission.PARTICIPACIONES_RESPONDER_PROPIAS)
    )
):
    try:
        data = await service.aceptar(current_user, invitacion_id)

    except _ERRORES as ex:
        raise _traducir(ex)

    return ResponsePayload.ok(
        data=data,
        message="Participación confirmada"
    )


@router.post(
    "/participante/invitaciones/{invitacion_id}/rechazar",
    response_model=ResponsePayload[InvitacionPropia],
    summary="Rechazar una invitación",
    responses={
        **_RESPUESTAS_COMUNES,
        404: {"description": "La invitación no existe o no es del usuario"},
        409: {"description": "Ya fue respondida, venció o fue cancelada"},
        422: {"description": "El motivo supera 255 caracteres"},
    },
)
async def rechazar_invitacion(
    invitacion_id: UUID,
    request: RechazoRequest | None = None,
    service: ParticipacionService = Depends(get_participacion_service),
    current_user: UserModel = Depends(
        require_permission(Permission.PARTICIPACIONES_RESPONDER_PROPIAS)
    )
):
    try:
        data = await service.rechazar(
            current_user,
            invitacion_id,
            request.motivo if request else None
        )

    except _ERRORES as ex:
        raise _traducir(ex)

    return ResponsePayload.ok(
        data=data,
        message="Respuesta registrada"
    )


# ── Administrador ───────────────────────────────────────────────────────

@router.get(
    "/admin/participaciones",
    response_model=ResponsePayload[ParticipacionesAdmin],
    summary="Supervisar participaciones",
    description=(
        "Invitaciones por actividad con conteos por pestaña y alertas. `q` "
        "busca por actividad, evento o participante sin distinguir "
        "mayúsculas ni tildes, y filtra también los conteos."
    ),
    responses=_RESPUESTAS_COMUNES,
)
async def listar_participaciones(
    filtro: Literal[
        "todas", "pendientes", "aceptadas", "por_reasignar", "error_envio"
    ] = Query("todas"),
    q: str | None = Query(None, max_length=100),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
    service: ParticipacionService = Depends(get_participacion_service),
    current_user: UserModel = Depends(
        require_permission(Permission.PARTICIPACIONES_SUPERVISAR)
    )
):
    data, total = await service.listar_admin(filtro, q, pagina, por_pagina)

    return ResponsePayload.ok(
        data=data,
        message="Participaciones obtenidas exitosamente",
        meta={"total": total, "pagina": pagina, "por_pagina": por_pagina}
    )


@router.post(
    "/admin/participaciones",
    response_model=ResponsePayload[ParticipacionAdmin],
    status_code=status.HTTP_201_CREATED,
    summary="Invitar a un participante a una actividad",
    description=(
        "Crea la invitación y la envía por correo. Una actividad solo admite "
        "una invitación activa: si ya tiene una, responde `409`. Si la "
        "anterior quedó liberada (rechazada, vencida o cancelada), pasa a "
        "`reasignada` y la nueva queda enlazada a ella."
    ),
    responses={
        **_RESPUESTAS_COMUNES,
        404: {"description": "Actividad no encontrada"},
        409: {"description": "La actividad ya tiene una invitación activa"},
        422: {"description": "Participante o plazo inválidos"},
    },
)
async def crear_invitacion(
    request: InvitacionCreate,
    service: ParticipacionService = Depends(get_participacion_service),
    current_user: UserModel = Depends(
        require_permission(Permission.PARTICIPACIONES_REASIGNAR)
    )
):
    try:
        data = await service.crear(
            current_user,
            request.actividad_id,
            request.participante_id,
            request.dias_para_confirmar
        )

    except _ERRORES as ex:
        raise _traducir(ex)

    return ResponsePayload.ok(
        data=data,
        status_code=status.HTTP_201_CREATED,
        message="Invitación creada"
    )


@router.get(
    "/admin/participaciones/eventos/{evento_id}",
    response_model=ResponsePayload[list[ParticipacionAdmin]],
    summary="Invitación vigente de cada actividad de un evento",
    responses=_RESPUESTAS_COMUNES,
)
async def participaciones_de_evento(
    evento_id: UUID,
    service: ParticipacionService = Depends(get_participacion_service),
    current_user: UserModel = Depends(
        require_permission(Permission.PARTICIPACIONES_SUPERVISAR)
    )
):
    data = await service.vigentes_de_evento(evento_id)

    return ResponsePayload.ok(
        data=data,
        message="Participaciones obtenidas exitosamente"
    )


@router.get(
    "/admin/participantes/elegibles",
    response_model=ResponsePayload[list[ParticipanteElegible]],
    summary="Usuarios que pueden recibir la invitación de una actividad",
    description=(
        "Usuarios activos (miembros y participantes), sin el asignado actual. "
        "`cruce_horario` marca, sin excluirlos, a quienes tienen otra "
        "actividad activa que se cruza."
    ),
    responses={
        **_RESPUESTAS_COMUNES,
        404: {"description": "Actividad no encontrada"},
    },
)
async def participantes_elegibles(
    actividad_id: UUID = Query(...),
    q: str | None = Query(None, max_length=100),
    service: ParticipacionService = Depends(get_participacion_service),
    current_user: UserModel = Depends(
        require_permission(Permission.PARTICIPACIONES_REASIGNAR)
    )
):
    try:
        data = await service.elegibles(actividad_id, q)

    except _ERRORES as ex:
        raise _traducir(ex)

    return ResponsePayload.ok(
        data=data,
        message="Participantes elegibles obtenidos exitosamente"
    )


@router.post(
    "/admin/participaciones/{invitacion_id}/cancelar",
    response_model=ResponsePayload[ParticipacionAdmin],
    summary="Cancelar una invitación pendiente",
    responses={
        **_RESPUESTAS_COMUNES,
        404: {"description": "Invitación no encontrada"},
        409: {"description": "La invitación ya no está pendiente"},
    },
)
async def cancelar_invitacion(
    invitacion_id: UUID,
    service: ParticipacionService = Depends(get_participacion_service),
    current_user: UserModel = Depends(
        require_permission(Permission.PARTICIPACIONES_CANCELAR)
    )
):
    try:
        data = await service.cancelar(current_user, invitacion_id)

    except _ERRORES as ex:
        raise _traducir(ex)

    return ResponsePayload.ok(
        data=data,
        message="Invitación cancelada"
    )


@router.post(
    "/admin/participaciones/{invitacion_id}/reenviar",
    response_model=ResponsePayload[ParticipacionAdmin],
    summary="Reenviar una invitación cuyo correo falló",
    description=(
        "Si el correo vuelve a fallar responde `200` con la fila en "
        "`estado_envio: error` y un mensaje claro, no un error de servidor."
    ),
    responses={
        **_RESPUESTAS_COMUNES,
        404: {"description": "Invitación no encontrada"},
        409: {"description": "No está pendiente o su envío no falló"},
    },
)
async def reenviar_invitacion(
    invitacion_id: UUID,
    service: ParticipacionService = Depends(get_participacion_service),
    current_user: UserModel = Depends(
        require_permission(Permission.PARTICIPACIONES_REENVIAR)
    )
):
    try:
        data, enviado = await service.reenviar(invitacion_id)

    except _ERRORES as ex:
        raise _traducir(ex)

    return ResponsePayload.ok(
        data=data,
        message=(
            "Invitación reenviada"
            if enviado
            else "No se pudo enviar el correo. La invitación sigue pendiente "
                 "y visible para el participante en la aplicación."
        )
    )


@router.get(
    "/admin/participaciones/{invitacion_id}/reasignacion",
    response_model=ResponsePayload[DatosReasignacion],
    summary="Datos para reasignar o revocar",
    responses={
        **_RESPUESTAS_COMUNES,
        404: {"description": "Invitación no encontrada"},
        409: {"description": "La invitación no admite reasignación"},
    },
)
async def datos_reasignacion(
    invitacion_id: UUID,
    service: ParticipacionService = Depends(get_participacion_service),
    current_user: UserModel = Depends(
        require_permission(Permission.PARTICIPACIONES_REASIGNAR)
    )
):
    try:
        data = await service.datos_reasignacion(invitacion_id)

    except _ERRORES as ex:
        raise _traducir(ex)

    return ResponsePayload.ok(
        data=data,
        message="Datos de reasignación obtenidos exitosamente"
    )


_RESPUESTAS_REEMPLAZO = {
    **_RESPUESTAS_COMUNES,
    404: {"description": "Invitación no encontrada"},
    409: {"description": "La invitación cambió de estado"},
    422: {"description": "Participante o plazo inválidos"},
}


@router.post(
    "/admin/participaciones/{invitacion_id}/reasignar",
    response_model=ResponsePayload[ReemplazoResultado],
    summary="Reasignar una actividad liberada",
    responses=_RESPUESTAS_REEMPLAZO,
)
async def reasignar_invitacion(
    invitacion_id: UUID,
    request: ReemplazoRequest,
    service: ParticipacionService = Depends(get_participacion_service),
    current_user: UserModel = Depends(
        require_permission(Permission.PARTICIPACIONES_REASIGNAR)
    )
):
    try:
        data = await service.reasignar(
            current_user,
            invitacion_id,
            request.participante_id,
            request.dias_para_confirmar
        )

    except _ERRORES as ex:
        raise _traducir(ex)

    return ResponsePayload.ok(
        data=data,
        message="Actividad reasignada"
    )


@router.post(
    "/admin/participaciones/{invitacion_id}/revocar",
    response_model=ResponsePayload[ReemplazoResultado],
    summary="Revocar una confirmación y cambiar de participante",
    responses=_RESPUESTAS_REEMPLAZO,
)
async def revocar_invitacion(
    invitacion_id: UUID,
    request: ReemplazoRequest,
    service: ParticipacionService = Depends(get_participacion_service),
    current_user: UserModel = Depends(
        require_permission(Permission.PARTICIPACIONES_REASIGNAR)
    )
):
    try:
        data = await service.revocar(
            current_user,
            invitacion_id,
            request.participante_id,
            request.dias_para_confirmar
        )

    except _ERRORES as ex:
        raise _traducir(ex)

    return ResponsePayload.ok(
        data=data,
        message="Confirmación revocada"
    )
