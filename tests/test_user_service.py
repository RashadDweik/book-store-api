from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status

import app.services.user_service as user_service_module
from app.repositories.user_repository import UserRepository
from app.repositories.role_repository import RoleRepository
from app.schemas.user import UserCreate, UserUpdate
from app.services.user_service import UserService


pytestmark = pytest.mark.anyio


async def test_register_creates_user(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: stub repository lookups and password hashing.
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_email = AsyncMock(return_value=None)
    roles = AsyncMock(spec=RoleRepository)
    user_role_id = uuid4()
    roles.get_id_by_name = AsyncMock(return_value=user_role_id)
    created_user = SimpleNamespace(id=uuid4())
    repo.create = AsyncMock(return_value=created_user)
    repo.get_by_id = AsyncMock(return_value=created_user)
    monkeypatch.setattr(user_service_module, "hash_password", lambda value: "hashed")
    service = UserService(repo, roles)
    data = UserCreate(email="user@example.com", full_name="Test User", password="Password1")

    # Act: register the user.
    result = await service.register(data)

    # Assert: user created with hashed password and no raw password stored.
    assert result is created_user
    repo.create.assert_awaited_once()
    repo.get_by_id.assert_awaited_once_with(created_user.id)
    payload = repo.create.call_args.args[0]
    assert payload["email"] == data.email
    assert payload["full_name"] == data.full_name
    assert payload["hashed_password"] == "hashed"
    assert payload["role_id"] == user_role_id
    assert "password" not in payload


async def test_register_rejects_duplicate_email() -> None:
    # Arrange: simulate an existing user with the same email.
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_email = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    roles = AsyncMock(spec=RoleRepository)
    service = UserService(repo, roles)
    data = UserCreate(email="user@example.com", full_name="Test User", password="Password1")

    # Act/Assert: registration rejects duplicates.
    with pytest.raises(HTTPException) as exc:
        await service.register(data)

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST


async def test_authenticate_rejects_missing_user() -> None:
    # Arrange: repository returns no user.
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_email = AsyncMock(return_value=None)
    roles = AsyncMock(spec=RoleRepository)
    service = UserService(repo, roles)

    # Act/Assert: authentication fails when user is missing.
    with pytest.raises(HTTPException) as exc:
        await service.authenticate("user@example.com", "Password1")

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


async def test_authenticate_rejects_invalid_password(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: user exists but password verification fails.
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_email = AsyncMock(
        return_value=SimpleNamespace(hashed_password="hashed", is_active=True)
    )
    roles = AsyncMock(spec=RoleRepository)
    monkeypatch.setattr(user_service_module, "verify_password", lambda plain, hashed: False)
    service = UserService(repo, roles)

    # Act/Assert: authentication fails with invalid password.
    with pytest.raises(HTTPException) as exc:
        await service.authenticate("user@example.com", "Password1")

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


async def test_authenticate_rejects_inactive_user(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: password checks pass but user is inactive.
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_email = AsyncMock(
        return_value=SimpleNamespace(hashed_password="hashed", is_active=False)
    )
    roles = AsyncMock(spec=RoleRepository)
    monkeypatch.setattr(user_service_module, "verify_password", lambda plain, hashed: True)
    service = UserService(repo, roles)

    # Act/Assert: authentication rejects inactive users.
    with pytest.raises(HTTPException) as exc:
        await service.authenticate("user@example.com", "Password1")

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


async def test_authenticate_returns_user(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: valid user with passing password verification.
    user = SimpleNamespace(hashed_password="hashed", is_active=True)
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_email = AsyncMock(return_value=user)
    roles = AsyncMock(spec=RoleRepository)
    monkeypatch.setattr(user_service_module, "verify_password", lambda plain, hashed: True)
    service = UserService(repo, roles)

    # Act: authenticate and return the user.
    result = await service.authenticate("user@example.com", "Password1")

    # Assert: the same user instance is returned.
    assert result is user


async def test_get_profile_returns_user() -> None:
    # Arrange: repository returns a user for the id.
    user = SimpleNamespace(id=uuid4())
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_id = AsyncMock(return_value=user)
    roles = AsyncMock(spec=RoleRepository)
    service = UserService(repo, roles)

    # Act: fetch the profile.
    result = await service.get_profile(user.id)

    # Assert: the fetched user is returned.
    assert result is user


async def test_get_profile_rejects_missing_user() -> None:
    # Arrange: repository returns no user for the id.
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_id = AsyncMock(return_value=None)
    roles = AsyncMock(spec=RoleRepository)
    service = UserService(repo, roles)

    # Act/Assert: missing profile raises a 404.
    with pytest.raises(HTTPException) as exc:
        await service.get_profile(uuid4())

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


async def test_update_profile_returns_existing_when_no_changes() -> None:
    # Arrange: repository returns a user and no update payload is provided.
    user = SimpleNamespace(id=uuid4())
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_id = AsyncMock(return_value=user)
    repo.update = AsyncMock()
    roles = AsyncMock(spec=RoleRepository)
    service = UserService(repo, roles)

    # Act: update with no changes.
    result = await service.update_profile(user.id, UserUpdate())

    # Assert: returns existing user without calling update.
    assert result is user
    repo.update.assert_not_awaited()


async def test_update_profile_applies_changes() -> None:
    # Arrange: repository returns a user and is set to return updated data.
    user = SimpleNamespace(id=uuid4())
    updated = SimpleNamespace(id=uuid4())
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_id = AsyncMock(side_effect=[user, updated])
    repo.update = AsyncMock(return_value=updated)
    roles = AsyncMock(spec=RoleRepository)
    service = UserService(repo, roles)
    data = UserUpdate(full_name="New Name")

    # Act: update with changes.
    result = await service.update_profile(user.id, data)

    # Assert: repository update called with the expected delta.
    assert result is updated
    repo.update.assert_awaited_once_with(user, {"full_name": "New Name"})


async def test_update_profile_rejects_missing_user() -> None:
    # Arrange: repository returns no user for the id.
    repo = AsyncMock(spec=UserRepository)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.update = AsyncMock()
    roles = AsyncMock(spec=RoleRepository)
    service = UserService(repo, roles)

    # Act/Assert: missing profile raises a 404.
    with pytest.raises(HTTPException) as exc:
        await service.update_profile(uuid4(), UserUpdate(full_name="New Name"))

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
