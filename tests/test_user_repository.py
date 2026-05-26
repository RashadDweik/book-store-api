from uuid import uuid4
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.user import User
from app.repositories.user_repository import UserRepository


pytestmark = pytest.mark.anyio


async def test_get_by_id_returns_user() -> None:
    # Arrange: mock the session execute result to return a user.
    user_id = uuid4()
    user = User(
        email="user@example.com",
        hashed_password="hashed",
        role_id=uuid4(),
    )
    result = Mock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repo = UserRepository(db)

    # Act: fetch by id through the repository.
    fetched = await repo.get_by_id(user_id)

    # Assert: returns the user and uses a select() statement.
    assert fetched is user
    db.execute.assert_awaited_once()
    stmt = db.execute.call_args.args[0]
    assert isinstance(stmt, Select)


async def test_get_by_email_returns_user() -> None:
    # Arrange: mock the session execute result to return a user.
    user = User(
        email="user@example.com",
        hashed_password="hashed",
        role_id=uuid4(),
    )
    result = Mock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repo = UserRepository(db)

    # Act: fetch by email through the repository.
    fetched = await repo.get_by_email("user@example.com")

    # Assert: returns the user and uses a select() statement.
    assert fetched is user
    db.execute.assert_awaited_once()
    stmt = db.execute.call_args.args[0]
    assert isinstance(stmt, Select)


async def test_create_persists_user() -> None:
    # Arrange: prepare a payload and session hooks.
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    repo = UserRepository(db)
    payload = {
        "email": "user@example.com",
        "hashed_password": "hashed",
        "role_id": uuid4(),
        "is_active": True,
    }

    # Act: create a user via the repository.
    created = await repo.create(payload)

    # Assert: user fields are set and persistence hooks were called.
    assert created.email == payload["email"]
    db.add.assert_called_once_with(created)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(created)


async def test_update_applies_changes() -> None:
    # Arrange: existing user and session hooks.
    """
    Verifies that UserRepository.update applies the provided changes to the given User and triggers session persistence.
    
    Asserts the passed User object is mutated (identity preserved) and that the session's add, flush, and refresh hooks are called exactly once with the updated user.
    """
    db = AsyncMock(spec=AsyncSession)
    db.add = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    repo = UserRepository(db)
    user = User(
        email="old@example.com",
        hashed_password="hashed",
        role_id=uuid4(),
    )

    # Act: update the user through the repository.
    updated = await repo.update(user, {"email": "new@example.com"})

    # Assert: fields updated and persistence hooks were called.
    assert updated is user
    assert user.email == "new@example.com"
    db.add.assert_called_once_with(user)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(user)
