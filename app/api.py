from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import HTMLResponse, Response

from app.dependencies import get_audio_processor, get_job_manager, get_job_store, get_transcription_service
from app.models import ExportRequest, JobCreateResponse, JobStatusResponse, JobSummaryResponse, TranscriptionResult
from app.services.audio import AudioProcessor
from app.services.export import export_json, export_txt
from app.services.jobs import JobManager, JobStore
from app.services.transcription import TranscriptionService

router = APIRouter()
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "index.html"


@router.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    with TEMPLATE_PATH.open("r", encoding="utf-8") as handle:
        return HTMLResponse(handle.read())


@router.post("/api/transcribe", response_model=TranscriptionResult)
async def transcribe(
    file: UploadFile = File(...),
    audio_processor: AudioProcessor = Depends(get_audio_processor),
    transcription_service: TranscriptionService = Depends(get_transcription_service),
) -> TranscriptionResult:
    source_path = audio_processor.save_upload(file)
    try:
        audio_processor.validate_duration(source_path)
        return transcription_service.transcribe(source_path, file.filename or source_path.name)
    finally:
        for extra_path in (source_path, source_path.with_name(f"{source_path.stem}-normalized.wav")):
            extra_path.unlink(missing_ok=True)


@router.post("/api/jobs", response_model=JobCreateResponse)
async def create_job(
    file: UploadFile = File(...),
    audio_processor: AudioProcessor = Depends(get_audio_processor),
    job_manager: JobManager = Depends(get_job_manager),
) -> JobCreateResponse:
    source_path = audio_processor.save_upload(file)
    duration_seconds = audio_processor.get_duration(source_path)
    job = job_manager.create_job(
        source_path=source_path,
        filename=file.filename or source_path.name,
        duration_seconds=duration_seconds,
    )
    return JobCreateResponse(job_id=job.job_id, status=job.status)


@router.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
) -> JobStatusResponse:
    return job_store.to_response(job_id)


@router.get("/api/jobs", response_model=list[JobSummaryResponse])
async def list_jobs(
    job_store: JobStore = Depends(get_job_store),
) -> list[JobSummaryResponse]:
    return job_store.list_responses()


@router.get("/api/jobs/{job_id}/result", response_model=TranscriptionResult)
async def get_job_result(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
) -> TranscriptionResult:
    response = job_store.to_response(job_id)
    if response.result is None:
        from fastapi import HTTPException, status

        if response.status == "failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=response.error or "Задача завершилась с ошибкой.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Результат ещё не готов.",
        )
    return response.result


@router.delete("/api/jobs/{job_id}")
async def delete_job(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
) -> dict[str, str]:
    job_store.delete(job_id)
    return {"status": "deleted"}


@router.delete("/api/jobs")
async def clear_jobs(
    job_store: JobStore = Depends(get_job_store),
) -> dict[str, str]:
    job_store.clear()
    return {"status": "cleared"}


@router.post("/api/export/txt")
async def export_transcript_txt(payload: ExportRequest) -> Response:
    content = export_txt(payload.result)
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="transcript.txt"'},
    )


@router.post("/api/export/json")
async def export_transcript_json(payload: ExportRequest) -> Response:
    content = export_json(payload.result)
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="transcript.json"'},
    )
