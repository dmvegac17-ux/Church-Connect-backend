from fastapi import APIRouter

from src.api.v1.auth.router import router as auth_router
from src.api.v1.health.router import router as health_router
from src.api.v1.users.router import router as users_router
from src.api.v1.announcements.router import router as announcements_router

router = APIRouter()

router.include_router(health_router)

router.include_router(auth_router)

router.include_router(
    users_router
)

router.include_router(
    announcements_router
)