from fastapi import FastAPI
from src.api.v1.router import router
from src.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.API_VERSION,
    debug=settings.DEBUG
)

app.include_router(
       router,
    prefix="/api/v1"
)