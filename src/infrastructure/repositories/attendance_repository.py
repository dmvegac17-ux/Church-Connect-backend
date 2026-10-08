from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.attendance_model import AttendanceModel


class AttendanceRepository:

    def __init__(
        self,
        db: AsyncSession
    ):
        self.db = db

    async def get_all(
        self,
        limit: int,
        offset: int,
        usuario_id: UUID | None = None,
        evento_id: UUID | None = None
    ):
        query = select(AttendanceModel)

        if usuario_id is not None:
            query = query.where(
                AttendanceModel.usuario_id == usuario_id
            )

        if evento_id is not None:
            query = query.where(
                AttendanceModel.evento_id == evento_id
            )

        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)

        return result.scalars().all()

    async def count(
        self,
        usuario_id: UUID | None = None,
        evento_id: UUID | None = None
    ) -> int:
        query = select(func.count()).select_from(
            AttendanceModel
        )

        if usuario_id is not None:
            query = query.where(
                AttendanceModel.usuario_id == usuario_id
            )

        if evento_id is not None:
            query = query.where(
                AttendanceModel.evento_id == evento_id
            )

        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_by_id(
        self,
        attendance_id: UUID
    ):
        query = select(AttendanceModel).where(
            AttendanceModel.id == attendance_id
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_by_user_and_event(
        self,
        usuario_id: UUID,
        evento_id: UUID
    ):
        query = select(AttendanceModel).where(
            AttendanceModel.usuario_id == usuario_id,
            AttendanceModel.evento_id == evento_id
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def create(
        self,
        attendance: AttendanceModel
    ):
        self.db.add(attendance)

        await self.db.commit()

        await self.db.refresh(attendance)

        return attendance

    async def update(
        self,
        attendance: AttendanceModel
    ):
        await self.db.commit()

        await self.db.refresh(attendance)

        return attendance

    async def delete(
        self,
        attendance: AttendanceModel
    ) -> None:
        await self.db.delete(attendance)

        await self.db.commit()
