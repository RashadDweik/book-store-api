from uuid import uuid4
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.auth_audit_log_service as audit_service_module
from app.services.auth_audit_log_service import AuthAuditLogService


pytestmark = pytest.mark.anyio


async def test_insert_event_commits_audit_row(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: session context manager returned by the session factory.
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    service = AuthAuditLogService()
    service._session_factory = Mock(return_value=session)

    repo_instance = Mock()
    repo_instance.create = AsyncMock()
    repo_class = Mock(return_value=repo_instance)
    monkeypatch.setattr(audit_service_module, "AuthAuditLogRepository", repo_class)

    user_id = uuid4()

    # Act: insert the event.
    await service.insert_event(
        user_id=user_id,
        event="login",
        ip_address="127.0.0.1",
        user_agent="pytest",
        refresh_token_hash="b" * 64,
    )

    # Assert: repository is called and transaction committed.
    repo_class.assert_called_once_with(session)
    repo_instance.create.assert_awaited_once()
    payload = repo_instance.create.call_args.args[0]
    assert payload["user_id"] == user_id
    assert payload["event"] == "login"
    assert payload["refresh_token_hash"] == "b" * 64
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


async def test_insert_event_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: make repository create fail.
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    service = AuthAuditLogService()
    service._session_factory = Mock(return_value=session)

    repo_instance = Mock()
    repo_instance.create = AsyncMock(side_effect=RuntimeError("boom"))
    repo_class = Mock(return_value=repo_instance)
    monkeypatch.setattr(audit_service_module, "AuthAuditLogRepository", repo_class)

    logger = Mock()
    monkeypatch.setattr(audit_service_module, "logger", logger)

    # Act: should not raise.
    await service.insert_event(user_id=uuid4(), event="logout")

    # Assert: rollback attempted and warning logged.
    session.rollback.assert_awaited_once()
    assert logger.warning.called
