from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.api.v1.attendances.schemas import AttendanceCreate, AttendanceUpdate
from src.application.attendances.services import (
    AttendanceOutsideEventWindowError,
    AttendanceService,
)


def make_service(event, existing_attendance=None):
    repository = SimpleNamespace(
        create=AsyncMock(side_effect=lambda attendance: attendance),
        get_by_id=AsyncMock(return_value=existing_attendance),
        get_by_user_and_event=AsyncMock(return_value=None),
        update=AsyncMock(side_effect=lambda attendance: attendance),
    )
    user_repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=object())
    )
    event_repository = SimpleNamespace(
        get_by_id=AsyncMock(return_value=event)
    )
    return AttendanceService(repository, user_repository, event_repository), repository


@pytest.mark.asyncio
async def test_create_rejects_attendance_before_event_starts():
    now = datetime.now(UTC)
    event = SimpleNamespace(
        fecha_inicio=now + timedelta(hours=1),
        fecha_fin=now + timedelta(hours=2),
    )
    service, repository = make_service(event)
    request = AttendanceCreate(
        usuario_id=uuid4(),
        evento_id=uuid4(),
        asistio=True,
    )

    with pytest.raises(AttendanceOutsideEventWindowError):
        await service.create(request, SimpleNamespace(id=uuid4()))

    repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_rejects_attendance_after_event_ends():
    now = datetime.now(UTC)
    attendance = SimpleNamespace(
        id=uuid4(),
        usuario_id=uuid4(),
        evento_id=uuid4(),
    )
    event = SimpleNamespace(
        fecha_inicio=now - timedelta(hours=2),
        fecha_fin=now - timedelta(hours=1),
    )
    service, repository = make_service(event, attendance)

    with pytest.raises(AttendanceOutsideEventWindowError):
        await service.update(attendance.id, AttendanceUpdate(asistio=False))

    repository.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_allows_attendance_during_event():
    now = datetime.now(UTC)
    event = SimpleNamespace(
        fecha_inicio=now - timedelta(hours=1),
        fecha_fin=now + timedelta(hours=1),
    )
    service, repository = make_service(event)
    request = AttendanceCreate(
        usuario_id=uuid4(),
        evento_id=uuid4(),
        asistio=True,
    )

    saved = await service.create(request, SimpleNamespace(id=uuid4()))

    assert saved.evento_id == request.evento_id
    repository.create.assert_awaited_once()