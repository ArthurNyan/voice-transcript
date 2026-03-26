import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    model_size: str = "small"
    compute_type: str = "default"
    language: str = "ru"
    temp_dir: Path = Path("tmp")
    max_upload_size_mb: int = 100


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        model_size=os.getenv("WHISPER_MODEL_SIZE", "small"),
        compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "default"),
        language=os.getenv("TRANSCRIPT_LANGUAGE", "ru"),
        temp_dir=Path(os.getenv("TEMP_DIR", "tmp")),
        max_upload_size_mb=int(os.getenv("MAX_UPLOAD_SIZE_MB", "100")),
    )
