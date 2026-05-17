from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Bookshop API")

    @app.get("/", tags=["health"])
    async def read_root() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
