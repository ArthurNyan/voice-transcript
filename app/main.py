from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import get_settings

BASE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    settings = get_settings()
    settings.temp_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Voice Transcript", version="0.1.0")
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    return app


app = create_app()
