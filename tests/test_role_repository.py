from uuid import uuid4
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.repositories.role_repository import RoleRepository


pytestmark = pytest.mark.anyio


async def test_get_id_by_name_returns_role_id() -> None:
    # Arrange: mock the session execute result to return a role id.
    role_id = uuid4()
    result = Mock()
    result.scalar_one_or_none.return_value = role_id
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repo = RoleRepository(db)

    # Act: fetch the role id through the repository.
    fetched = await repo.get_id_by_name("user")

    # Assert: returns the id and uses a select() statement.
    assert fetched == role_id
    db.execute.assert_awaited_once()
    stmt = db.execute.call_args.args[0]
    assert isinstance(stmt, Select)


async def test_get_id_by_name_returns_none_when_missing() -> None:
    # Arrange: mock the session execute result to return no rows.
    result = Mock()
    result.scalar_one_or_none.return_value = None
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=result)
    repo = RoleRepository(db)

    # Act: fetch a missing role id.
    fetched = await repo.get_id_by_name("missing")

    # Assert: None is returned and the query is executed.
    assert fetched is None
    db.execute.assert_awaited_once()
    stmt = db.execute.call_args.args[0]
    assert isinstance(stmt, Select)
