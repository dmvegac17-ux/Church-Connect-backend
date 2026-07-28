from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status

from src.api.dependencies.auth import get_auth_service
from src.api.v1.auth.schemas import LoginRequest
from src.api.v1.auth.schemas import TokenResponse
from src.application.auth.services import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


@router.post(
    "/login",
    response_model=TokenResponse
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

    return TokenResponse(access_token=access_token)
