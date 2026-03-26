from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import get_audio_processor, get_job_manager, get_job_store, get_transcription_service
from app.main import create_app
from app.models import Segment, TranscriptionResult
from app.services.jobs import JobStore


class FakeAudioProcessor:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path

    def save_upload(self, upload):
        destination = self.tmp_path / (upload.filename or "audio.webm")
        destination.write_bytes(upload.file.read())
        return destination

    def validate_duration(self, source_path: Path) -> float:
        return 1.2

    def get_duration(self, source_path: Path) -> float:
        return 1.2


class FakeJobManager:
    def __init__(self, store: JobStore) -> None:
        self.store = store

    def create_job(self, source_path: Path, filename: str, duration_seconds: float):
        job = self.store.create(filename=filename, source_path=source_path, duration_seconds=duration_seconds)
        job.status = "done"
        job.progress = 1.0
        job.current_step = "done"
        job.result = TranscriptionResult(
            text="Привет мир",
            segments=[Segment(start=0.0, end=1.2, text="Привет мир")],
            language="ru",
            duration_seconds=duration_seconds,
            filename=filename,
        )
        self.store.update(job)
        source_path.unlink(missing_ok=True)
        return job


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
    store = JobStore(Settings(temp_dir=tmp_path))
    app.dependency_overrides[get_audio_processor] = lambda: FakeAudioProcessor(tmp_path)
    app.dependency_overrides[get_transcription_service] = lambda: FakeTranscriptionService()
    app.dependency_overrides[get_job_store] = lambda: store
    app.dependency_overrides[get_job_manager] = lambda: FakeJobManager(store)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
