from abc import ABC
from abc import abstractmethod
from uuid import UUID

from src.infrastructure.database.models.user_model import UserModel


class IUserRepository(ABC):

    @abstractmethod
    async def get_all(
        self,
        limit: int,
        offset: int
    ) -> list[UserModel]:
        pass

    @abstractmethod
    async def get_by_id(
        self,
        user_id: UUID
    ) -> UserModel | None:
        pass

    @abstractmethod
    async def get_by_email(
        self,
        email: str
    ) -> UserModel | None:
        pass

    @abstractmethod
    async def create(
        self,
        user: UserModel
    ) -> UserModel:
        pass

    @abstractmethod
    async def delete(
        self,
        user: UserModel
    ) -> None:
        pass