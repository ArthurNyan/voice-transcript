from pathlib import Path
from typing import Protocol

from fastapi import HTTPException, status

from app.config import Settings
from app.models import Segment, TranscriptionResult
from app.services.audio import AudioProcessor


class WhisperModelProtocol(Protocol):
    def transcribe(self, audio: str, language: str, vad_filter: bool):
        ...


class TranscriptionService:
    def __init__(self, settings: Settings, audio_processor: AudioProcessor) -> None:
        self.settings = settings
        self.audio_processor = audio_processor
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Не удалось импортировать faster-whisper.",
                ) from exc

            try:
                self._model = WhisperModel(
                    self.settings.model_size,
                    device="auto",
                    compute_type=self.settings.compute_type,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Не удалось загрузить модель транскрибации.",
                ) from exc
        return self._model

    def transcribe(self, source_path: Path, original_filename: str) -> TranscriptionResult:
        normalized_path, duration_seconds = self.audio_processor.normalize(source_path)
        model = self._get_model()

        try:
            segments, info = model.transcribe(
                str(normalized_path),
                language=self.settings.language,
                vad_filter=True,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка во время транскрибации аудио.",
            ) from exc

        structured_segments = [
            Segment(
                start=round(segment.start, 2),
                end=round(segment.end, 2),
                text=segment.text.strip(),
            )
            for segment in segments
            if segment.text.strip()
        ]
        text = " ".join(segment.text for segment in structured_segments).strip()

        if not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось распознать речь. Попробуйте более длинную или более чистую запись.",
            )

        return TranscriptionResult(
            text=text,
            segments=structured_segments,
            language=getattr(info, "language", self.settings.language),
            duration_seconds=duration_seconds,
            filename=original_filename,
        )
