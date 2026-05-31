from fastapi import APIRouter
from src.api.v1.health.router import router as health_router

router = APIRouter()

router.include_router(health_router)