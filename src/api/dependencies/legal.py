from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.legal.services import LegalService
from src.infrastructure.database.session import get_db


def get_legal_service(
    db: AsyncSession = Depends(get_db)
) -> LegalService:
    return LegalService(db)
