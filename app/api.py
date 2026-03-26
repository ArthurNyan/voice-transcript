from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import HTMLResponse, Response

from app.dependencies import get_audio_processor, get_transcription_service
from app.models import ExportRequest, TranscriptionResult
from app.services.audio import AudioProcessor
from app.services.export import export_json, export_txt
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
        return transcription_service.transcribe(source_path, file.filename or source_path.name)
    finally:
        for extra_path in (source_path, source_path.with_name(f"{source_path.stem}-normalized.wav")):
            extra_path.unlink(missing_ok=True)


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
