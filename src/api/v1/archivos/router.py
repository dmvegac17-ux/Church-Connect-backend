from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from src.api.dependencies.archivos import get_archivos_service
from src.api.v1.archivos.schemas import ArchivoCreate
from src.api.v1.archivos.schemas import ArchivoResponse
from src.api.v1.archivos.schemas import ArchivoUpdate
from src.application.archivos.services import ArchivosService
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.security.permissions import require_roles
from src.infrastructure.database.models.user_model import UserModel




router = APIRouter(
    prefix="/archivos",
    tags=["Archivos"]
)


@router.get(
    "",
    response_model=ResponsePayload[list[ArchivoResponse]],
    summary="Listar archivos",
    description=(
        "Devuelve un listado paginado de archivos. "
        "Cualquier usuario autenticado puede consultar los archivos."
    ),
    responses={
        401: {"description": "No autenticado"},
    },
)
async def get_archivos(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: ArchivosService = Depends(
        get_archivos_service
    ),
    current_user: UserModel = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.PARTICIPANT,
            UserRole.MEMBER
        )
    )
):
    archivos = await service.get_all(
        limit=limit,
        offset=offset
    )

    total = await service.count()

    return ResponsePayload.ok(
        data=archivos,
        message="Archivos obtenidos exitosamente",
        meta={"totalArchivos": total}
    )


@router.get(
    "/{archivo_id}",
    response_model=ResponsePayload[ArchivoResponse],
    summary="Obtener archivo por ID",
    description=(
        "Devuelve el detalle de un archivo específico. "
        "Cualquier usuario autenticado puede consultar archivos."
    ),
    responses={
        401: {"description": "No autenticado"},
        404: {"description": "Archivo no encontrado"},
    },
)
async def get_archivo(
    archivo_id: UUID,
    service: ArchivosService = Depends(
        get_archivos_service
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
        archivo = await service.get_by_id(
            archivo_id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=archivo,
        message="Archivo obtenido exitosamente"
    )


@router.post(
    "",
    response_model=ResponsePayload[ArchivoResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Crear archivo",
    description=(
        "Registra un nuevo archivo en la plataforma. "
        "Solo el rol `admin` puede crear archivos."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
    },
)
async def create_archivo(
    request: ArchivoCreate,
    service: ArchivosService = Depends(
        get_archivos_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        archivo = await service.create(
            request=request,
            user_id=current_user.id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=archivo,
        status_code=status.HTTP_201_CREATED,
        message="Archivo creado exitosamente"
    )


@router.put(
    "/{archivo_id}",
    response_model=ResponsePayload[ArchivoResponse],
    summary="Actualizar archivo",
    description=(
        "Actualiza los datos de un archivo existente. "
        "Solo el rol `admin` puede actualizar archivos."
    ),
    responses={
        400: {"description": "Datos inválidos"},
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Archivo no encontrado"},
    },
)
async def update_archivo(
    archivo_id: UUID,
    request: ArchivoUpdate,
    service: ArchivosService = Depends(
        get_archivos_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        archivo = await service.update(
            archivo_id=archivo_id,
            request=request
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=archivo,
        message="Archivo actualizado exitosamente"
    )


@router.delete(
    "/{archivo_id}",
    response_model=ResponsePayload[None],
    summary="Eliminar archivo",
    description=(
        "Elimina un archivo existente. "
        "Solo el rol `admin` puede eliminar archivos."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No tiene permisos para realizar esta acción"},
        404: {"description": "Archivo no encontrado"},
    },
)
async def delete_archivo(
    archivo_id: UUID,
    service: ArchivosService = Depends(
        get_archivos_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        await service.delete(
            archivo_id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=None,
        message="Archivo eliminado exitosamente"
    )