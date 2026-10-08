from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from src.api.dependencies.auth import get_auth_service
from src.api.dependencies.users import get_user_service
from src.api.v1.auth.schemas import LoginRequest
from src.api.v1.auth.schemas import RegisterRequest
from src.api.v1.auth.schemas import TokenResponse
from src.api.v1.users.schemas import UserCreate
from src.api.v1.users.schemas import UserResponse
from src.application.auth.services import AuthService
from src.application.users.services import UserService
from src.core.constants.enums import UserRole
from src.core.schemas.response import ResponsePayload

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
        "Permite que cualquier persona cree su propia cuenta. El rol queda "
        "fijo en `member`; para obtener otro rol un administrador debe "
        "actualizarlo posteriormente con `PUT /users/{id}`."
    ),
    responses={
        400: {"description": "Datos inválidos o correo ya registrado"},
    },
)
async def register(
    request: RegisterRequest,
    service: UserService = Depends(
        get_user_service
    )
):
    try:
        user = await service.create(
            UserCreate(
                nombre=request.nombre,
                apellido=request.apellido,
                correo=request.correo,
                contrasena=request.contrasena,
                telefono=request.telefono,
                rol=UserRole.MEMBER,
                activo=True
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
