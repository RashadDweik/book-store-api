import os

import httpx
import pytest

os.environ["DATABASE_URL"] = "postgresql+asyncpg://test_user:test_pass@localhost:5432/test_db"
os.environ["SECRET_KEY"] = "test-secret"

import app.main as app_main


class FakeConnection:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    async def execute(self, statement) -> None:
        if self.should_fail:
            raise RuntimeError("database unavailable")


class FakeConnectionContext:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    async def __aenter__(self) -> FakeConnection:
        return FakeConnection(should_fail=self.should_fail)

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeEngine:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def connect(self) -> FakeConnectionContext:
        return FakeConnectionContext(should_fail=self.should_fail)


class FakeRedis:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    async def ping(self) -> None:
        if self.should_fail:
            raise RuntimeError("redis unavailable")


@pytest.fixture
def app() -> app_main.FastAPI:
    app = app_main.create_app()
    app.state.inventory_cache.redis = FakeRedis()
    app.state.refresh_token_store.redis = FakeRedis()
    yield app
    app.dependency_overrides.clear()


def test_normalize_allowed_origins_disables_wildcard_in_production() -> None:
    assert app_main._normalize_allowed_origins(["*"], debug=False) == []
    assert app_main._normalize_allowed_origins(["*"], debug=True) == ["*"]
    assert app_main._normalize_allowed_origins('["https://example.com"]', debug=False) == [
        "https://example.com"
    ]


@pytest.mark.anyio
async def test_ready_returns_ok_when_dependencies_are_available(
    monkeypatch: pytest.MonkeyPatch,
    app: app_main.FastAPI,
) -> None:
    monkeypatch.setattr(app_main, "engine", FakeEngine())

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {
        "database": "ok",
        "inventory_cache": "ok",
        "refresh_token_store": "ok",
    }


@pytest.mark.anyio
async def test_ready_returns_503_when_database_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    app: app_main.FastAPI,
) -> None:
    monkeypatch.setattr(app_main, "engine", FakeEngine(should_fail=True))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["status"] == "degraded"
    assert body["detail"]["checks"]["database"] == "error"
    assert "database" in body["detail"]["errors"]