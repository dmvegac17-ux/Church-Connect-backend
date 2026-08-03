from datetime import datetime, UTC
from http import HTTPStatus
from typing import Generic
from typing import TypeVar

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

T = TypeVar("T")


def status_name(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase.replace(" ", "")
    except ValueError:
        return "Error"


class ResponsePayload(BaseModel, Generic[T]):
    model_config = ConfigDict(populate_by_name=True)

    status_code: int = Field(alias="statusCode")
    status: str | None = None
    data: T | None = None
    success: bool
    message: str | None = None
    errors: list[str] | None = None
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    meta: dict | None = None

    @classmethod
    def ok(
        cls,
        data: T | None = None,
        status_code: int = 200,
        message: str | None = None,
        meta: dict | None = None
    ) -> "ResponsePayload[T]":
        return cls(
            status_code=status_code,
            status=status_name(status_code),
            data=data,
            success=True,
            message=message,
            meta=meta
        )
