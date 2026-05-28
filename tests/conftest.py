import os
import pytest
from app.core.limiter import limiter

try:
    from limits.storage import storage_from_uri

    def build_limiter_storage():
        return storage_from_uri("memory://")

except ImportError:
    try:
        from limits.storage import MemoryStorage
    except ImportError:
        from limits.storage.memory import MemoryStorage

    def build_limiter_storage():
        # Fallback for older limits versions without storage_from_uri.
        return MemoryStorage()


def reset_limiter_state() -> None:
    storage = limiter._storage
    reset = getattr(storage, "reset", None)
    if callable(reset):
        reset()
        return
    clear = getattr(storage, "clear", None)
    if callable(clear):
        clear()


def _apply_limiter_storage(target, storage) -> None:
    for attr_name in ("storage", "_storage", "storage_backend", "_storage_backend"):
        if hasattr(target, attr_name):
            try:
                setattr(target, attr_name, storage)
            except (AttributeError, TypeError):
                pass


@pytest.fixture(autouse=True)
def limiter_memory_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the rate limiter to use in-memory storage for all tests
    monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "memory://")
    from app.core.config import get_settings

    get_settings.cache_clear()
    storage = build_limiter_storage()
    _apply_limiter_storage(limiter, storage)
    for attr_name in ("storage_uri", "_storage_uri"):
        if hasattr(limiter, attr_name):
            monkeypatch.setattr(limiter, attr_name, "memory://", raising=False)
    for attr_name in ("limiter", "_limiter", "rate_limiter", "_rate_limiter"):
        rate_limiter = getattr(limiter, attr_name, None)
        if rate_limiter is None:
            continue
        _apply_limiter_storage(rate_limiter, storage)
    
    reset_limiter_state()
