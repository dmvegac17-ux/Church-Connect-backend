from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi import status

from src.api.dependencies.auth import get_auth_service
from src.api.dependencies.auth import get_current_user
from src.api.dependencies.auth import get_password_reset_service
from src.api.dependencies.legal import get_legal_service
from src.api.dependencies.users import get_user_service
from src.api.v1.auth.schemas import ForgotPasswordRequest
from src.api.v1.auth.schemas import LoginRequest
from src.api.v1.auth.schemas import RegisterRequest
from src.api.v1.auth.schemas import ResetPasswordRequest
from src.api.v1.auth.schemas import TokenResponse
from src.api.v1.legal.router import origen
from src.api.v1.users.schemas import UserCreate
from src.api.v1.users.schemas import UserResponse
from src.application.auth.password_reset import DemasiadasSolicitudesError
from src.application.auth.password_reset import EnlaceError
from src.application.auth.password_reset import MINUTOS_DE_VIGENCIA
from src.application.auth.password_reset import PasswordResetService
from src.application.auth.services import AuthService
from src.application.legal.services import DocumentoLegalError
from src.application.legal.services import LegalService
from src.application.users.services import UserService
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload
from src.core.security.jwt import create_access_token
from src.infrastructure.database.models.user_model import UserModel

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


@router.post(
    "/register",
    response_model=ResponsePayload[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Registrarse",
    description=(
        "Permite que cualquier persona cree su propia cuenta. Debe enviar "
        "en `documentos_aceptados` los ids de las versiones vigentes de los "
        "documentos legales (`GET /legal/documentos`); la aceptación queda "
        "registrada con la cuenta. El rol queda "
        "fijo en `member`; para obtener otro rol un administrador debe "
        "actualizarlo posteriormente con `PUT /users/{id}`."
    ),
    responses={
        400: {"description": "Datos inválidos o correo ya registrado"},
    },
)
async def register(
    datos: RegisterRequest,
    request: Request,
    service: UserService = Depends(
        get_user_service
    ),
    legal: LegalService = Depends(
        get_legal_service
    )
):
    try:
        documentos = await legal.validar_para_registro(datos.documentos_aceptados)

    except DocumentoLegalError as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(ex), "codigo": ex.codigo}
        )

    ip, navegador = origen(request)

    try:
        user = await service.create(
            UserCreate(
                nombre=datos.nombre,
                apellido=datos.apellido,
                correo=datos.correo,
                contrasena=datos.contrasena,
                telefono=datos.telefono,
                rol=UserRole.MEMBER,
                activo=True
            ),
            # La constancia de aceptación se guarda en la misma transacción
            # que la cuenta: o quedan las dos, o ninguna.
            junto_con=lambda usuario: LegalService.constancias(
                usuario.id, documentos, ip, navegador
            )
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=400,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=user,
        status_code=status.HTTP_201_CREATED,
        message="Usuario registrado exitosamente"
    )


@router.post(
    "/login",
    response_model=ResponsePayload[TokenResponse],
    summary="Iniciar sesión",
    description=(
        "Valida las credenciales del usuario y devuelve un access token JWT. "
        "Cópialo y pégalo en el botón **Authorize** de Swagger (esquema "
        "Bearer) para autenticar los endpoints protegidos."
    ),
    responses={
        401: {"description": "Credenciales inválidas"},
    },
)
async def login(
    request: LoginRequest,
    service: AuthService = Depends(
        get_auth_service
    )
):
    try:
        access_token = await service.login(request)

    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=TokenResponse(access_token=access_token),
        message="Inicio de sesión exitoso"
    )


@router.post(
    "/refresh",
    response_model=ResponsePayload[TokenResponse],
    summary="Renovar la sesión",
    description=(
        "Cambia un access token todavía vigente por uno nuevo con la "
        "expiración completa. El cliente lo llama mientras la persona está "
        "usando la aplicación, para que la sesión no se cierre en medio del "
        "trabajo; quien deja de usarla no renueva y su token vence solo. El "
        "rol del token nuevo es el actual del usuario."
    ),
    responses={
        401: {"description": "Token inválido o expirado, o usuario inactivo"},
    },
)
async def refresh(
    current_user: UserModel = Depends(get_current_user)
):
    # Desactivar a alguien corta su sesión en la siguiente renovación.
    if current_user.activo is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El usuario está inactivo"
        )

    return ResponsePayload.ok(
        data=TokenResponse(
            access_token=create_access_token(
                user_id=current_user.id,
                rol=current_user.rol
            )
        ),
        message="Sesión renovada"
    )


# ── Restablecer la contraseña por correo ────────────────────────────────

_RESPUESTA_GENERICA = (
    "Si el correo está registrado, recibirás un enlace para restablecer tu "
    f"contraseña. Vence en {MINUTOS_DE_VIGENCIA} minutos."
)


def _ip(request: Request) -> str:
    # Detrás de un proxy (Render, Vercel…), la IP real viene en esta cabecera.
    reenviada = request.headers.get("x-forwarded-for", "")

    return reenviada.split(",")[0].strip() or (
        request.client.host if request.client else "desconocida"
    )


def _enlace_invalido(ex: EnlaceError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"message": str(ex), "codigo": ex.codigo}
    )


@router.post(
    "/olvide-contrasena",
    response_model=ResponsePayload[None],
    summary="Pedir el enlace para restablecer la contraseña",
    description=(
        "Envía al correo un enlace de un solo uso para elegir una contraseña "
        "nueva. La respuesta es siempre la misma, exista o no una cuenta con "
        "ese correo, para no revelar quién está registrado. Hay un límite de "
        "solicitudes por cuenta y por dirección IP."
    ),
    responses={
        429: {"description": "Demasiadas solicitudes desde esta dirección"},
    },
)
async def olvide_contrasena(
    datos: ForgotPasswordRequest,
    request: Request,
    service: PasswordResetService = Depends(
        get_password_reset_service
    )
):
    try:
        await service.solicitar(datos.correo, _ip(request))

    except DemasiadasSolicitudesError as ex:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(ex)
        )

    return ResponsePayload.ok(
        data=None,
        message=_RESPUESTA_GENERICA
    )


@router.get(
    "/restablecer-contrasena/validar",
    response_model=ResponsePayload[None],
    summary="Comprobar un enlace de restablecimiento",
    description=(
        "Dice si el enlace sigue sirviendo, sin consumirlo. Si no, responde "
        "`400` con `data.codigo`: `enlace_invalido`, `enlace_vencido` o "
        "`enlace_usado`."
    ),
    responses={
        400: {"description": "El enlace no es válido, venció o ya se usó"},
    },
)
async def validar_enlace(
    token: str = Query(..., min_length=10, max_length=200),
    service: PasswordResetService = Depends(
        get_password_reset_service
    )
):
    try:
        await service.validar(token)

    except EnlaceError as ex:
        raise _enlace_invalido(ex)

    return ResponsePayload.ok(
        data=None,
        message="El enlace es válido"
    )


@router.post(
    "/restablecer-contrasena",
    response_model=ResponsePayload[None],
    summary="Elegir una contraseña nueva con el enlace del correo",
    description=(
        "Cambia la contraseña de la cuenta a la que pertenece el enlace. El "
        "enlace queda consumido, se anulan los demás pendientes de esa "
        "cuenta y se cierran sus sesiones abiertas."
    ),
    responses={
        400: {"description": "El enlace no es válido, venció o ya se usó"},
    },
)
async def restablecer_contrasena(
    datos: ResetPasswordRequest,
    service: PasswordResetService = Depends(
        get_password_reset_service
    )
):
    try:
        await service.restablecer(datos.token, datos.contrasena)

    except EnlaceError as ex:
        raise _enlace_invalido(ex)

    return ResponsePayload.ok(
        data=None,
        message="Tu contraseña se cambió. Ya puedes iniciar sesión."
    )
