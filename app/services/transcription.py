from pathlib import Path
from typing import Callable, Optional, Protocol

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
        try:
            structured_segments, language = self._transcribe_normalized(normalized_path, 0.0)
        finally:
            normalized_path.unlink(missing_ok=True)

        text = " ".join(segment.text for segment in structured_segments).strip()

        if not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось распознать речь. Попробуйте более длинную или более чистую запись.",
            )

        return TranscriptionResult(
            text=text,
            segments=structured_segments,
            language=language,
            duration_seconds=duration_seconds,
            filename=original_filename,
        )

    def transcribe_long(
        self,
        source_path: Path,
        original_filename: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> TranscriptionResult:
        normalized_path, duration_seconds = self.audio_processor.normalize(source_path)
        if progress_callback is not None:
            progress_callback(0.12, "splitting")

        chunk_duration_seconds = getattr(self.settings, "chunk_duration_seconds", 60)
        chunk_files = self.audio_processor.split_normalized_audio(normalized_path, chunk_duration_seconds)
        if not chunk_files:
            normalized_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось подготовить чанки для транскрибации.",
            )

        all_segments: list[Segment] = []
        language = self.settings.language
        elapsed_offset = 0.0
        total_chunks = len(chunk_files)

        try:
            for index, (chunk_path, chunk_duration) in enumerate(chunk_files, start=1):
                chunk_segments, language = self._transcribe_normalized(chunk_path, elapsed_offset)
                all_segments.extend(chunk_segments)
                elapsed_offset += chunk_duration
                if progress_callback is not None:
                    progress = 0.12 + (index / total_chunks) * 0.82
                    progress_callback(progress, "transcribing")
        finally:
            normalized_path.unlink(missing_ok=True)
            for chunk_path, _ in chunk_files:
                chunk_path.unlink(missing_ok=True)

        text = " ".join(segment.text for segment in all_segments).strip()
        if not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось распознать речь. Попробуйте более длинную или более чистую запись.",
            )

        if progress_callback is not None:
            progress_callback(0.97, "assembling")

        return TranscriptionResult(
            text=text,
            segments=all_segments,
            language=language,
            duration_seconds=duration_seconds,
            filename=original_filename,
        )

    def _transcribe_normalized(self, normalized_path: Path, offset_seconds: float) -> tuple[list[Segment], str]:
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

        structured_segments = []
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            structured_segments.append(
                Segment(
                    start=round(offset_seconds + segment.start, 2),
                    end=round(offset_seconds + segment.end, 2),
                    text=text,
                )
            )

        return structured_segments, getattr(info, "language", self.settings.language)
