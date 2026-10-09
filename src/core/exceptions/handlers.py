from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.core.logging.logger import logger
from src.core.schemas.response import ResponsePayload
from src.core.schemas.response import status_name


def _build_response(
    status_code: int,
    message: str,
    errors: list[str] | None = None,
    data: dict | None = None
) -> JSONResponse:
    payload = ResponsePayload(
        status_code=status_code,
        status=status_name(status_code),
        data=data,
        success=False,
        message=message,
        errors=errors
    )

    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", by_alias=True)
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException
) -> JSONResponse:
    # `detail` como dict: `message` va al envelope y el resto viaja en `data`
    # (p. ej. `estado_actual` en un 409) para que el cliente pueda reaccionar.
    if isinstance(exc.detail, dict):
        detail = dict(exc.detail)
        message = str(detail.pop("message", "Error"))

        return _build_response(
            status_code=exc.status_code,
            message=message,
            errors=[message],
            data=detail or None
        )

    return _build_response(
        status_code=exc.status_code,
        message=str(exc.detail),
        errors=[str(exc.detail)]
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    errors = [
        f"{'.'.join(str(loc) for loc in error['loc'])}: {error['msg']}"
        for error in exc.errors()
    ]

    return _build_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message="Error de validación en los datos enviados",
        errors=errors
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    logger.exception(
        "Excepción no controlada en %s %s",
        request.method,
        request.url.path
    )

    return _build_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Error interno del servidor",
        errors=["Ocurrió un error inesperado. Contacte al administrador."]
    )
