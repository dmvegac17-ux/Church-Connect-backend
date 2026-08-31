from fastapi import APIRouter

from src.api.v1.attendances.router import router as attendances_router
from src.api.v1.auth.router import router as auth_router
from src.api.v1.health.router import router as health_router
from src.api.v1.users.router import router as users_router
from src.api.v1.announcements.router import router as announcements_router
from src.api.v1.notificaciones.router import router as notificaciones_router
from src.api.v1.events.router import router as events_router
from src.api.v1.ministries.router import router as ministries_router
from src.api.v1.registrations.router import router as registrations_router
from src.api.v1.schedules.router import router as schedules_router
from src.api.v1.archivos.router import router as archivos_router
from src.api.v1.confirmaciones_email.router import router as confirmaciones_email_router

router = APIRouter()

router.include_router(health_router)

router.include_router(auth_router)

router.include_router(
    users_router
)

router.include_router(
    announcements_router
)
router.include_router(
    notificaciones_router
)
router.include_router(events_router)
router.include_router(ministries_router)
router.include_router(schedules_router)
router.include_router(archivos_router)
router.include_router(registrations_router)
router.include_router(attendances_router)
router.include_router(confirmaciones_email_router)
