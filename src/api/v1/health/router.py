from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.schemas.response import ResponsePayload
from src.infrastructure.database.session import get_db

router = APIRouter(tags=["Health"])


@router.get(
    "/health/db",
    response_model=ResponsePayload[dict],
    summary="Verificar conexión a la base de datos",
    description="Ejecuta un `SELECT 1` contra la base de datos para confirmar conectividad.",
    responses={
        503: {"description": "No se pudo conectar a la base de datos"},
    },
)
async def health_db(
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            text("SELECT 1")
        )
    except (SQLAlchemyError, OSError) as ex:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se pudo conectar a la base de datos: {ex}"
        )

    return ResponsePayload.ok(
        data={"database": result.scalar()},
        message="Conexión a la base de datos exitosa"
    )