from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import Form
from fastapi import HTTPException
from fastapi import Query
from fastapi import UploadFile
from fastapi import status

from src.api.dependencies.announcements import get_announcement_service
from src.api.v1.announcements.schemas import AnnouncementResponse
from src.application.announcements.services import IMAGEN_MAX_BYTES
from src.application.announcements.services import AnnouncementService
from src.application.announcements.services import AnuncioNoEncontradoError
from src.application.announcements.services import DatosAnuncioInvalidosError
from src.application.announcements.services import ImagenSubida
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.security.permissions import require_roles
from src.infrastructure.database.models.user_model import UserModel
from src.infrastructure.supabase.client import StorageError
from src.infrastructure.supabase.client import StorageNoConfiguradoError


router = APIRouter(
    prefix="/announcements",
    tags=["Announcements"]
)

_RESPUESTAS_ESCRITURA = {
    401: {"description": "No autenticado"},
    403: {"description": "No tiene permisos para realizar esta acción"},
    422: {
        "description": (
            "Datos inválidos: título o texto vacíos o demasiado largos, o "
            "imagen que no es JPG, PNG o WebP o supera 5 MB"
        )
    },
    502: {"description": "No se pudo subir la imagen a Storage"},
    503: {"description": "La subida de imágenes no está configurada"},
}


async def _leer_imagen(imagen: UploadFile | None) -> ImagenSubida | None:
    """
    Lee el archivo con un tope de 5 MB + 1 byte: basta para saber si se pasa
    del límite sin cargar en memoria un archivo enorme.
    """
    if imagen is None or not imagen.filename:
        return None

    contenido = await imagen.read(IMAGEN_MAX_BYTES + 1)

    return ImagenSubida(contenido=contenido, nombre=imagen.filename)


def _traducir(ex: Exception) -> HTTPException:
    if isinstance(ex, AnuncioNoEncontradoError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ex)
        )

    if isinstance(ex, DatosAnuncioInvalidosError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(ex), "campo": ex.campo}
        )

    if isinstance(ex, StorageNoConfiguradoError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(ex)
        )

    if isinstance(ex, StorageError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(ex)
        )

    raise ex


_ERRORES = (
    AnuncioNoEncontradoError,
    DatosAnuncioInvalidosError,
    StorageNoConfiguradoError,
    StorageError,
)


@router.get(
    "",
    response_model=ResponsePayload[list[AnnouncementResponse]],
    summary="Listar anuncios",
    description=(
        "Listado paginado, del más reciente al más antiguo, con el nombre de "
        "quien publicó y de quien actualizó. Cualquier usuario con sesión "
        "puede consultarlo."
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
        "Cualquier usuario con sesión puede consultar anuncios."
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
            UserRole.MEMBER
        )
    )
):
    try:
        announcement = await service.get_by_id(
            announcement_id
        )

    except _ERRORES as ex:
        raise _traducir(ex)

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
        "Formulario `multipart/form-data` con `titulo`, `contenido` e "
        "`imagen` opcional (JPG, PNG o WebP, máximo 5 MB). Quien publica es "
        "siempre el usuario autenticado. Solo el rol `admin`."
    ),
    responses=_RESPUESTAS_ESCRITURA,
)
async def create_announcement(
    titulo: str = Form(...),
    contenido: str = Form(...),
    imagen: UploadFile | None = File(None),
    service: AnnouncementService = Depends(
        get_announcement_service
    ),
    current_user: UserModel = Depends(
        require_roles(UserRole.ADMIN)
    )
):
    try:
        announcement = await service.create(
            autor=current_user,
            titulo=titulo,
            contenido=contenido,
            imagen=await _leer_imagen(imagen)
        )

    except _ERRORES as ex:
        raise _traducir(ex)

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
        "Formulario `multipart/form-data`; todos los campos son opcionales. "
        "`imagen` reemplaza la actual (la anterior se borra del bucket) y "
        "`quitar_imagen=true` la elimina. Quien actualiza es siempre el "
        "usuario autenticado. Solo el rol `admin`."
    ),
    responses={
        **_RESPUESTAS_ESCRITURA,
        404: {"description": "Anuncio no encontrado"},
    },
)
async def update_announcement(
    announcement_id: UUID,
    titulo: str | None = Form(None),
    contenido: str | None = Form(None),
    imagen: UploadFile | None = File(None),
    quitar_imagen: bool = Form(False),
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
            editor=current_user,
            titulo=titulo,
            contenido=contenido,
            imagen=await _leer_imagen(imagen),
            quitar_imagen=quitar_imagen
        )

    except _ERRORES as ex:
        raise _traducir(ex)

    return ResponsePayload.ok(
        data=announcement,
        message="Anuncio actualizado exitosamente"
    )


@router.delete(
    "/{announcement_id}",
    response_model=ResponsePayload[None],
    summary="Eliminar anuncio",
    description=(
        "Elimina el anuncio y, después, su imagen del bucket. "
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

    except _ERRORES as ex:
        raise _traducir(ex)

    return ResponsePayload.ok(
        data=None,
        message="Anuncio eliminado exitosamente"
    )
