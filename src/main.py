from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.router import router
from src.core.config import settings
from src.core.exceptions.handlers import http_exception_handler
from src.core.exceptions.handlers import unhandled_exception_handler
from src.core.exceptions.handlers import validation_exception_handler

tags_metadata = [
    {
        "name": "Auth",
        "description": "Autenticación y emisión de tokens JWT.",
    },
    {
        "name": "Users",
        "description": "Gestión de usuarios de la plataforma.",
    },
    {
        "name": "Health",
        "description": "Endpoints de verificación de estado de la API y la base de datos.",
    },
]

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.API_VERSION,
    # Nota: FastAPI/Starlette con debug=True muestra el traceback crudo como
    # respuesta HTTP para cualquier 500 no controlado, ignorando por completo
    # los exception_handlers registrados abajo. Se mantiene en False para que
    # la API siempre responda con el envelope JSON de ResponsePayload; el
    # traceback completo igual queda en logs vía unhandled_exception_handler.
    debug=False,
    description=(
        "API REST de Church Connect: gestión de usuarios, roles, eventos, "
        "ministerios, horarios, registros y anuncios de la iglesia."
    ),
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(
    router,
    prefix="/api/v1"
)