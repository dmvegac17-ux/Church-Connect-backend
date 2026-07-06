from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from src.api.dependencies.users import get_user_service
from src.api.v1.users.schemas import UserCreate
from src.api.v1.users.schemas import UserResponse
from src.api.v1.users.schemas import UserUpdate
from src.application.users.services import UserService


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.get(
    "",
    response_model=list[UserResponse]
)
async def get_users(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: UserService = Depends(
        get_user_service
    )
):
    return await service.get_all(
        limit=limit,
        offset=offset
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse
)
async def get_user(
    user_id: UUID,
    service: UserService = Depends(
        get_user_service
    )
):
    try:
        return await service.get_by_id(
            user_id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=404,
            detail=str(ex)
        )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_user(
    request: UserCreate,
    service: UserService = Depends(
        get_user_service
    )
):
    try:
        return await service.create(
            request
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=400,
            detail=str(ex)
        )


@router.put(
    "/{user_id}",
    response_model=UserResponse
)
async def update_user(
    user_id: UUID,
    request: UserUpdate,
    service: UserService = Depends(
        get_user_service
    )
):
    try:
        return await service.update(
            user_id,
            request
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=400,
            detail=str(ex)
        )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_user(
    user_id: UUID,
    service: UserService = Depends(
        get_user_service
    )
):
    try:
        await service.delete(
            user_id
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=404,
            detail=str(ex)
        )