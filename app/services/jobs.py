from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status

from app.config import Settings
from app.models import JobStatusResponse, JobSummaryResponse, TranscriptionResult
from app.services.transcription import TranscriptionService


@dataclass
class TranscriptionJob:
    job_id: str
    filename: str
    source_path: Path
    status: str = "queued"
    progress: float = 0.0
    current_step: str = "queued"
    error: Optional[str] = None
    duration_seconds: float = 0.0
    result: Optional[TranscriptionResult] = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class JobStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jobs: dict[str, TranscriptionJob] = {}
        self._lock = threading.Lock()
        self.jobs_dir = self.settings.temp_dir / self.settings.jobs_dir_name
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._load_from_disk()

    def create(self, filename: str, source_path: Path, duration_seconds: float) -> TranscriptionJob:
        job = TranscriptionJob(
            job_id=uuid.uuid4().hex,
            filename=filename,
            source_path=source_path,
            duration_seconds=duration_seconds,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        self._persist(job)
        return job

    def get(self, job_id: str) -> TranscriptionJob:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Задача не найдена.",
            )
        return job

    def to_response(self, job_id: str) -> JobStatusResponse:
        job = self.get(job_id)
        with job.lock:
            return JobStatusResponse(
                job_id=job.job_id,
                status=job.status,
                progress=job.progress,
                current_step=job.current_step,
                filename=job.filename,
                error=job.error,
                duration_seconds=job.duration_seconds,
                result=job.result,
            )

    def list_responses(self) -> list[JobSummaryResponse]:
        with self._lock:
            jobs = list(self._jobs.values())
        summaries: list[JobSummaryResponse] = []
        for job in sorted(jobs, key=lambda item: item.job_id, reverse=True):
            with job.lock:
                summaries.append(
                    JobSummaryResponse(
                        job_id=job.job_id,
                        status=job.status,
                        progress=job.progress,
                        current_step=job.current_step,
                        filename=job.filename,
                        error=job.error,
                        duration_seconds=job.duration_seconds,
                    )
                )
        return summaries

    def update(self, job: TranscriptionJob) -> None:
        self._persist(job)

    def delete(self, job_id: str) -> None:
        job = self.get(job_id)
        with self._lock:
            self._jobs.pop(job_id, None)
        if job.source_path.exists():
            job.source_path.unlink(missing_ok=True)
        self._job_path(job_id).unlink(missing_ok=True)

    def clear(self) -> None:
        with self._lock:
            job_ids = list(self._jobs.keys())
        for job_id in job_ids:
            self.delete(job_id)

    def _job_path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"

    def _persist(self, job: TranscriptionJob) -> None:
        payload = {
            "job_id": job.job_id,
            "filename": job.filename,
            "source_path": str(job.source_path),
            "status": job.status,
            "progress": job.progress,
            "current_step": job.current_step,
            "error": job.error,
            "duration_seconds": job.duration_seconds,
            "result": job.result.model_dump() if job.result else None,
        }
        self._job_path(job.job_id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_from_disk(self) -> None:
        for path in sorted(self.jobs_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            status_value = payload.get("status", "queued")
            if status_value == "processing":
                status_value = "failed"
                payload["current_step"] = "failed"
                payload["error"] = "Задача была прервана перезапуском приложения."
                payload["progress"] = 1.0
            job = TranscriptionJob(
                job_id=payload["job_id"],
                filename=payload["filename"],
                source_path=Path(payload.get("source_path") or ""),
                status=status_value,
                progress=payload.get("progress", 0.0),
                current_step=payload.get("current_step", "queued"),
                error=payload.get("error"),
                duration_seconds=payload.get("duration_seconds", 0.0),
                result=TranscriptionResult.model_validate(payload["result"]) if payload.get("result") else None,
            )
            self._jobs[job.job_id] = job
            self._persist(job)


class JobManager:
    def __init__(self, store: JobStore, transcription_service: TranscriptionService) -> None:
        self.store = store
        self.transcription_service = transcription_service

    def create_job(self, source_path: Path, filename: str, duration_seconds: float) -> TranscriptionJob:
        job = self.store.create(filename=filename, source_path=source_path, duration_seconds=duration_seconds)
        worker = threading.Thread(target=self._run_job, args=(job.job_id,), daemon=True)
        worker.start()
        return job

    def _run_job(self, job_id: str) -> None:
        job = self.store.get(job_id)
        with job.lock:
            job.status = "processing"
            job.current_step = "preparing"
            job.progress = 0.05
        self.store.update(job)

        try:
            result = self.transcription_service.transcribe_long(
                job.source_path,
                job.filename,
                progress_callback=lambda progress, step: self._update_progress(job_id, progress, step),
            )
        except Exception as exc:
            with job.lock:
                job.status = "failed"
                job.current_step = "failed"
                job.progress = 1.0
                job.error = getattr(exc, "detail", str(exc))
            self.store.update(job)
        else:
            with job.lock:
                job.status = "done"
                job.current_step = "done"
                job.progress = 1.0
                job.result = result
            self.store.update(job)
        finally:
            job.source_path.unlink(missing_ok=True)

    def _update_progress(self, job_id: str, progress: float, step: str) -> None:
        job = self.store.get(job_id)
        with job.lock:
            job.progress = max(0.0, min(progress, 0.99 if step != "done" else 1.0))
            job.current_step = step
        self.store.update(job)
