from fastapi import FastAPI

from app.core.config import Settings, get_settings

def create_app() -> FastAPI:
    settings: Settings = get_settings()
    app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)
    app.state.settings = settings

    @app.get("/", tags=["health"])
    async def read_root() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
