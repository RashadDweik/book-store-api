from uuid import uuid4
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.auth_audit_log_repository import AuthAuditLogRepository


pytestmark = pytest.mark.anyio


async def test_create_persists_auth_audit_log() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    repo = AuthAuditLogRepository(db)

    payload = {
        "user_id": uuid4(),
        "event": "login",
        "ip_address": "127.0.0.1",
        "user_agent": "pytest",
        "refresh_token_hash": "a" * 64,
    }

    created = await repo.create(payload)

    assert created.user_id == payload["user_id"]
    assert created.event == payload["event"]
    assert created.refresh_token_hash == payload["refresh_token_hash"]

    db.add.assert_called_once_with(created)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(created)
