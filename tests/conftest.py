from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_audio_processor, get_transcription_service
from app.main import create_app
from app.models import Segment, TranscriptionResult


class FakeAudioProcessor:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path

    def save_upload(self, upload):
        destination = self.tmp_path / (upload.filename or "audio.webm")
        destination.write_bytes(upload.file.read())
        return destination


class FakeTranscriptionService:
    def transcribe(self, source_path: Path, original_filename: str) -> TranscriptionResult:
        return TranscriptionResult(
            text="Привет мир",
            segments=[Segment(start=0.0, end=1.2, text="Привет мир")],
            language="ru",
            duration_seconds=1.2,
            filename=original_filename,
        )


@pytest.fixture()
def client(tmp_path: Path):
    app = create_app()
    app.dependency_overrides[get_audio_processor] = lambda: FakeAudioProcessor(tmp_path)
    app.dependency_overrides[get_transcription_service] = lambda: FakeTranscriptionService()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
