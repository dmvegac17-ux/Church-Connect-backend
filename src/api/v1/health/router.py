from sqlalchemy import text
from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.session import get_db

router = APIRouter(tags=["Health"])


@router.get("/health/db")
async def health_db(
    db: AsyncSession = Depends(get_db)
):

    result = await db.execute(
        text("SELECT 1")
    )

    return {
        "database": result.scalar()
    }