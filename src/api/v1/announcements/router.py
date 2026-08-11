from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from src.api.dependencies.announcements import get_announcement_service
from src.api.v1.announcements.schemas import AnnouncementCreate
from src.api.v1.announcements.schemas import AnnouncementResponse
from src.api.v1.announcements.schemas import AnnouncementUpdate
from src.application.announcements.services import AnnouncementService
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.security.permissions import require_roles
from src.infrastructure.database.models.user_model import UserModel


router = APIRouter(
    prefix="/announcements",
    tags=["Announcements"]
)


@router.get(
    "",
    response_model=ResponsePayload[list[AnnouncementResponse]],
    summary="Listar anuncios",
    description=(
        "Devuelve un listado paginado de anuncios. "
        "Cualquier usuario autenticado puede consultar los anuncios."
    ),
    responses={
        401: {"description": "No autenticado"},
    },
)
async def get_announcements(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: AnnouncementService = Depends(
        get_announcement_service
    ),
    current_user: UserModel = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.PARTICIPANT,
            UserRole.MEMBER
        )
    )
):
    announcements = await service.get_all(
        limit=limit,
        offset=offset
    )

    total = await service.count()

    return ResponsePayload.ok(
        data=announcements,
        message="Anuncios obtenidos exitosamente",
        meta={"totalAnnouncements": total}
    )


@router.get(
    "/{announcement_id}",
    response_model=ResponsePayload[AnnouncementResponse],
    summary="Obtener anuncio por ID",
    description=(
        "Devuelve el detalle de un anuncio específico. "
        "Cualquier usuario autenticado puede consultar anuncios."
    ),
    responses={
        401: {"description": "No autenticado"},
        404: {"description": "Anuncio no encontrado"},
    },
)
async def get_announcement(
    announcement_id: UUID,
    service: AnnouncementService = Depends(
        get_announcement_service
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
        announcement = await service.get_by_id(
            announcement_id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=announcement,
        message="Anuncio obtenido exitosamente"
    )


@router.post(
    "",
    response_model=ResponsePayload[AnnouncementResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Crear anuncio",
    description=(
        "Registra un nuevo anuncio en la plataforma. "
        "Solo el rol `admin` puede crear anuncios."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
    },
)
async def create_announcement(
    request: AnnouncementCreate,
    service: AnnouncementService = Depends(
        get_announcement_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        announcement = await service.create(
            request=request,
            user_id=current_user.id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=announcement,
        status_code=status.HTTP_201_CREATED,
        message="Anuncio creado exitosamente"
    )


@router.put(
    "/{announcement_id}",
    response_model=ResponsePayload[AnnouncementResponse],
    summary="Actualizar anuncio",
    description=(
        "Actualiza los datos de un anuncio existente. "
        "Solo el rol `admin` puede actualizar anuncios."
    ),
    responses={
        400: {"description": "Datos inválidos"},
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Anuncio no encontrado"},
    },
)
async def update_announcement(
    announcement_id: UUID,
    request: AnnouncementUpdate,
    service: AnnouncementService = Depends(
        get_announcement_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        announcement = await service.update(
            announcement_id=announcement_id,
            request=request
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=announcement,
        message="Anuncio actualizado exitosamente"
    )


@router.delete(
    "/{announcement_id}",
    response_model=ResponsePayload[None],
    summary="Eliminar anuncio",
    description=(
        "Elimina un anuncio existente. "
        "Solo el rol `admin` puede eliminar anuncios."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Anuncio no encontrado"},
    },
)
async def delete_announcement(
    announcement_id: UUID,
    service: AnnouncementService = Depends(
        get_announcement_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        await service.delete(
            announcement_id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=None,
        message="Anuncio eliminado exitosamente"
    )