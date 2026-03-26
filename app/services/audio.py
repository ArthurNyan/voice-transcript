import json
import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import Settings

SUPPORTED_EXTENSIONS = {".webm", ".wav", ".mp3", ".m4a", ".mp4", ".mpeg"}


class AudioProcessor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def save_upload(self, upload: UploadFile) -> Path:
        self.settings.temp_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неподдерживаемый формат файла.",
            )

        destination = self.settings.temp_dir / f"{uuid.uuid4().hex}{suffix}"
        size = 0

        with destination.open("wb") as handle:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > self.settings.max_upload_size_mb * 1024 * 1024:
                    destination.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Файл превышает допустимый размер.",
                    )
                handle.write(chunk)

        if size == 0:
            destination.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Файл пустой.",
            )

        return destination

    def normalize(self, source_path: Path) -> tuple[Path, float]:
        self.settings.temp_dir.mkdir(parents=True, exist_ok=True)
        if shutil.which("ffmpeg") is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="ffmpeg не найден. Установите его через Homebrew: brew install ffmpeg",
            )

        normalized_path = self.settings.temp_dir / f"{source_path.stem}-normalized.wav"
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(normalized_path),
        ]

        process = subprocess.run(command, capture_output=True, text=True)
        if process.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось обработать аудиофайл.",
            )

        return normalized_path, self.get_duration(normalized_path)

    def validate_duration(self, source_path: Path) -> float:
        duration_seconds = self.get_duration(source_path)
        max_duration_seconds = self.settings.max_audio_duration_minutes * 60

        if duration_seconds and duration_seconds > max_duration_seconds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Аудио слишком длинное для синхронной обработки. "
                    f"Максимум: {self.settings.max_audio_duration_minutes} минут."
                ),
            )

        return duration_seconds

    def split_normalized_audio(
        self,
        source_path: Path,
        chunk_duration_seconds: int,
    ) -> list[tuple[Path, float]]:
        self.settings.temp_dir.mkdir(parents=True, exist_ok=True)
        chunk_pattern = self.settings.temp_dir / f"{source_path.stem}-chunk-%03d.wav"
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-f",
            "segment",
            "-segment_time",
            str(chunk_duration_seconds),
            "-c",
            "copy",
            str(chunk_pattern),
        ]
        process = subprocess.run(command, capture_output=True, text=True)
        if process.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось разбить аудио на части.",
            )

        chunks = sorted(self.settings.temp_dir.glob(f"{source_path.stem}-chunk-*.wav"))
        return [(chunk, self.get_duration(chunk)) for chunk in chunks]

    def get_duration(self, source_path: Path) -> float:
        if shutil.which("ffprobe") is None:
            return 0.0

        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(source_path),
        ]
        process = subprocess.run(command, capture_output=True, text=True)
        if process.returncode != 0:
            return 0.0

        payload = json.loads(process.stdout or "{}")
        return round(float(payload.get("format", {}).get("duration", 0.0)), 2)
