"""FastAPI application factory and middleware setup."""

import logging
import time
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api.v1.router import api_router
from app.api.v1.routers import realtime as realtime_router
from app.core.config import Settings, get_settings
from app.core.inventory_cache import build_inventory_cache
from app.core.limiter import limiter
from app.core.refresh_token_store import build_refresh_token_store
from app.core.realtime import WebSocketHub


# Configure structured logging once at import time.
logging.basicConfig(level=logging.INFO, format="%(message)s")
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Log request duration with method, path, and status code."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "request.complete",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        return response


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings: Settings = get_settings()
    # Enable Sentry error reporting when configured.
    if settings.SENTRY_DSN:
        sentry_sdk.init(dsn=settings.SENTRY_DSN)

    # Log startup and shutdown events for service visibility.
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("app.startup", service=settings.APP_NAME)
        yield
        inventory_cache = getattr(app.state, "inventory_cache", None)
        if inventory_cache is not None:
            await inventory_cache.close()
        refresh_store = getattr(app.state, "refresh_token_store", None)
        if refresh_store is not None:
            await refresh_store.close()
        logger.info("app.shutdown", service=settings.APP_NAME)

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )
    # Store shared objects on app.state for later use.
    app.state.settings = settings
    app.state.limiter = limiter
    app.state.inventory_cache = build_inventory_cache(settings)
    app.state.refresh_token_store = build_refresh_token_store(settings)
    app.state.websocket_hub = WebSocketHub()

    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(RequestTimingMiddleware)
    # Normalize ALLOWED_ORIGINS to a list in case it was provided as a JSON
    # string or comma-separated env value.
    allow_origins = settings.ALLOWED_ORIGINS
    if isinstance(allow_origins, str):
        try:
            import json

            parsed = json.loads(allow_origins)
            if isinstance(parsed, list):
                allow_origins = parsed
            else:
                # backstop to comma-split strings
                allow_origins = [s.strip() for s in allow_origins.split(",") if s.strip()]
        except Exception:
            allow_origins = [s.strip() for s in allow_origins.split(",") if s.strip()]

    logger.info("cors.config", allowed_origins=allow_origins)

    # Do not use a wildcard origin when credentials are enabled. Browser
    # requests that include cookies require the backend to echo an explicit
    # frontend origin instead of "*".

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok", "service": settings.APP_NAME}

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(realtime_router.router)

    return app


app = create_app()
