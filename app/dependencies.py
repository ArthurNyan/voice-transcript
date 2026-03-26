from functools import lru_cache

from app.config import get_settings
from app.services.audio import AudioProcessor
from app.services.transcription import TranscriptionService


@lru_cache(maxsize=1)
def get_audio_processor() -> AudioProcessor:
    return AudioProcessor(get_settings())


@lru_cache(maxsize=1)
def get_transcription_service() -> TranscriptionService:
    return TranscriptionService(get_settings(), get_audio_processor())
