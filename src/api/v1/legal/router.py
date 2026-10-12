from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi import status

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.legal import get_legal_service
from src.api.v1.legal.schemas import AceptacionPropia
from src.api.v1.legal.schemas import AceptarRequest
from src.api.v1.legal.schemas import BorradorUpdate
from src.api.v1.legal.schemas import DocumentoAdmin
from src.api.v1.legal.schemas import DocumentoPendiente
from src.api.v1.legal.schemas import DocumentoPublico
from src.api.v1.legal.schemas import PublicarRequest
from src.api.v1.legal.schemas import ResumenAceptaciones
from src.api.v1.legal.schemas import TipoDocumento
from src.application.legal.services import DocumentoLegalError
from src.application.legal.services import DocumentoNoEncontradoError
from src.application.legal.services import LegalService
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.security.permissions import require_roles
from src.infrastructure.database.models.user_model import UserModel

router = APIRouter(
    prefix="/legal",
    tags=["Documentos legales"]
)


def origen(request: Request) -> tuple[str | None, str | None]:
    """IP y navegador de quien acepta, para la constancia."""
    reenviada = request.headers.get("x-forwarded-for", "")
    ip = reenviada.split(",")[0].strip() or (
        request.client.host if request.client else None
    )

    return ip, request.headers.get("user-agent")


def _no_encontrado(ex: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))


def _conflicto(ex: DocumentoLegalError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"message": str(ex), "codigo": ex.codigo}
    )


# ── Público: leer lo vigente ────────────────────────────────────────────

@router.get(
    "/documentos",
    response_model=ResponsePayload[list[DocumentoPublico]],
    summary="Documentos legales vigentes",
    description=(
        "La versión publicada de los Términos y condiciones y de la Política "
        "de privacidad. No requiere sesión: cualquiera puede leerlos antes "
        "de registrarse."
    ),
)
async def documentos_vigentes(
    service: LegalService = Depends(get_legal_service)
):
    return ResponsePayload.ok(
        data=await service.vigentes(),
        message="Documentos obtenidos exitosamente"
    )


@router.get(
    "/documentos/{tipo}",
    response_model=ResponsePayload[DocumentoPublico],
    summary="Un documento legal vigente",
    description="La versión publicada de `terminos` o `privacidad`. No requiere sesión.",
    responses={404: {"description": "Ese documento aún no está publicado"}},
)
async def documento_vigente(
    tipo: TipoDocumento,
    service: LegalService = Depends(get_legal_service)
):
    try:
        documento = await service.vigente(tipo)

    except DocumentoNoEncontradoError as ex:
        raise _no_encontrado(ex)

    return ResponsePayload.ok(
        data=documento,
        message="Documento obtenido exitosamente"
    )


# ── Con sesión: lo propio ───────────────────────────────────────────────
# Estas rutas usan `get_current_user` a secas: deben responder aunque la
# persona tenga una aceptación pendiente (son las que le permiten resolverla).

@router.get(
    "/mis-pendientes",
    response_model=ResponsePayload[list[DocumentoPendiente]],
    summary="Documentos que debo aceptar",
    description=(
        "Los documentos vigentes que la persona autenticada todavía no ha "
        "aceptado. Mientras haya alguno, el resto de la API le responde "
        "`403` con `data.codigo = 'aceptacion_pendiente'`."
    ),
)
async def mis_pendientes(
    service: LegalService = Depends(get_legal_service),
    current_user: UserModel = Depends(get_current_user)
):
    return ResponsePayload.ok(
        data=await service.pendientes(current_user.id),
        message="Pendientes obtenidos exitosamente"
    )


@router.post(
    "/aceptaciones",
    response_model=ResponsePayload[list[DocumentoPendiente]],
    summary="Aceptar los documentos pendientes",
    description=(
        "Deja constancia de que la persona autenticada acepta las versiones "
        "vigentes que tenía pendientes, con fecha, IP y navegador. Hay que "
        "enviar exactamente esas versiones: si alguna cambió entre tanto, "
        "responde `409` para que las vuelva a leer."
    ),
    responses={409: {"description": "Los documentos cambiaron: hay que revisarlos de nuevo"}},
)
async def aceptar(
    datos: AceptarRequest,
    request: Request,
    service: LegalService = Depends(get_legal_service),
    current_user: UserModel = Depends(get_current_user)
):
    try:
        aceptados = await service.aceptar(current_user, datos.documentos, *origen(request))

    except DocumentoLegalError as ex:
        raise _conflicto(ex)

    return ResponsePayload.ok(
        data=aceptados,
        message="Aceptación registrada"
    )


@router.get(
    "/mis-aceptaciones",
    response_model=ResponsePayload[list[AceptacionPropia]],
    summary="Mi historial de aceptaciones",
    description="Qué versiones aceptó la persona autenticada y cuándo. Solo las propias.",
)
async def mis_aceptaciones(
    service: LegalService = Depends(get_legal_service),
    current_user: UserModel = Depends(get_current_user)
):
    return ResponsePayload.ok(
        data=await service.aceptaciones_de(current_user.id),
        message="Aceptaciones obtenidas exitosamente"
    )


# ── Administración ──────────────────────────────────────────────────────

@router.get(
    "/admin/documentos",
    response_model=ResponsePayload[list[DocumentoAdmin]],
    summary="Todas las versiones de los documentos",
    description="Vigentes, borradores e historial de versiones archivadas. Solo `admin`.",
)
async def listar_versiones(
    service: LegalService = Depends(get_legal_service),
    current_user: UserModel = Depends(require_roles(UserRole.ADMIN))
):
    return ResponsePayload.ok(
        data=await service.todos(),
        message="Documentos obtenidos exitosamente"
    )


@router.post(
    "/admin/documentos/{tipo}/borrador",
    response_model=ResponsePayload[DocumentoAdmin],
    status_code=status.HTTP_201_CREATED,
    summary="Crear el borrador de la siguiente versión",
    description=(
        "Crea un borrador con el texto de la versión vigente, para editarlo "
        "sin tocar lo ya aceptado. Si ya hay un borrador de ese tipo, "
        "devuelve ese. Solo `admin`."
    ),
)
async def crear_borrador(
    tipo: TipoDocumento,
    service: LegalService = Depends(get_legal_service),
    current_user: UserModel = Depends(require_roles(UserRole.ADMIN))
):
    return ResponsePayload.ok(
        data=await service.crear_borrador(tipo, current_user),
        status_code=status.HTTP_201_CREATED,
        message="Borrador listo para editar"
    )


@router.put(
    "/admin/documentos/{documento_id}",
    response_model=ResponsePayload[DocumentoAdmin],
    summary="Guardar un borrador",
    description=(
        "Actualiza el título y el contenido (Markdown) de un borrador. Una "
        "versión publicada o archivada no se puede modificar. Solo `admin`."
    ),
    responses={
        404: {"description": "Documento no encontrado"},
        409: {"description": "No es un borrador"},
    },
)
async def guardar_borrador(
    documento_id: UUID,
    datos: BorradorUpdate,
    service: LegalService = Depends(get_legal_service),
    current_user: UserModel = Depends(require_roles(UserRole.ADMIN))
):
    try:
        documento = await service.actualizar_borrador(
            documento_id, datos.titulo, datos.contenido, current_user
        )

    except DocumentoNoEncontradoError as ex:
        raise _no_encontrado(ex)

    except DocumentoLegalError as ex:
        raise _conflicto(ex)

    return ResponsePayload.ok(
        data=documento,
        message="Borrador guardado"
    )


@router.delete(
    "/admin/documentos/{documento_id}",
    response_model=ResponsePayload[None],
    summary="Descartar un borrador",
    description="Elimina un borrador. Lo publicado y lo archivado no se elimina. Solo `admin`.",
    responses={
        404: {"description": "Documento no encontrado"},
        409: {"description": "No es un borrador"},
    },
)
async def descartar_borrador(
    documento_id: UUID,
    service: LegalService = Depends(get_legal_service),
    current_user: UserModel = Depends(require_roles(UserRole.ADMIN))
):
    try:
        await service.eliminar_borrador(documento_id)

    except DocumentoNoEncontradoError as ex:
        raise _no_encontrado(ex)

    except DocumentoLegalError as ex:
        raise _conflicto(ex)

    return ResponsePayload.ok(
        data=None,
        message="Borrador descartado"
    )


@router.post(
    "/admin/documentos/{documento_id}/publicar",
    response_model=ResponsePayload[DocumentoAdmin],
    summary="Publicar un borrador",
    description=(
        "Convierte el borrador en la versión vigente y archiva la anterior. "
        "Con `requiere_reaceptacion: true` la versión sube a N.0 y todas las "
        "personas deben volver a aceptar; con `false` sube a N.M+1 y no se "
        "le pide nada a quien ya había aceptado. Solo `admin`."
    ),
    responses={
        404: {"description": "Documento no encontrado"},
        409: {"description": "No es un borrador, o está vacío"},
    },
)
async def publicar(
    documento_id: UUID,
    datos: PublicarRequest,
    service: LegalService = Depends(get_legal_service),
    current_user: UserModel = Depends(require_roles(UserRole.ADMIN))
):
    try:
        documento = await service.publicar(
            documento_id, datos.requiere_reaceptacion, current_user
        )

    except DocumentoNoEncontradoError as ex:
        raise _no_encontrado(ex)

    except DocumentoLegalError as ex:
        raise _conflicto(ex)

    return ResponsePayload.ok(
        data=documento,
        message=f"Versión {documento.version} publicada"
    )


@router.get(
    "/admin/aceptaciones",
    response_model=ResponsePayload[ResumenAceptaciones],
    summary="Quién aceptó los documentos vigentes",
    description=(
        "Por cada persona activa: qué versión aceptó de cada documento y "
        "cuándo, o si la tiene pendiente. Solo `admin`."
    ),
)
async def resumen_de_aceptaciones(
    service: LegalService = Depends(get_legal_service),
    current_user: UserModel = Depends(require_roles(UserRole.ADMIN))
):
    return ResponsePayload.ok(
        data=await service.resumen_de_aceptaciones(),
        message="Aceptaciones obtenidas exitosamente"
    )


@router.get(
    "/admin/usuarios/{usuario_id}/aceptaciones",
    response_model=ResponsePayload[list[AceptacionPropia]],
    summary="Historial de aceptaciones de una persona",
    description="Todas las versiones que aceptó esa persona y cuándo. Solo `admin`.",
)
async def aceptaciones_de_usuario(
    usuario_id: UUID,
    service: LegalService = Depends(get_legal_service),
    current_user: UserModel = Depends(require_roles(UserRole.ADMIN))
):
    return ResponsePayload.ok(
        data=await service.aceptaciones_de(usuario_id),
        message="Aceptaciones obtenidas exitosamente"
    )
