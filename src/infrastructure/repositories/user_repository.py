from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.user_model import UserModel


class UserRepository:

    def __init__(
        self,
        db: AsyncSession
    ):
        self.db = db

    async def get_all(
        self,
        limit: int,
        offset: int
    ):
        query = (
            select(UserModel)
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def get_by_id(
        self,
        user_id: UUID
    ):
        query = select(UserModel).where(
            UserModel.id == user_id
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_by_email(
        self,
        email: str
    ):
        query = select(UserModel).where(
            UserModel.correo == email
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def create(
        self,
        user: UserModel
    ):
        self.db.add(user)

        await self.db.commit()

        await self.db.refresh(user)

        return user

    async def delete(
        self,
        user: UserModel
    ):
        await self.db.delete(user)

        await self.db.commit()
    
    async def update(
            self,
            user: UserModel
    ):
         await self.db.commit()
         await self.db.refresh(user)
         return user