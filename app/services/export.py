import json

from app.models import TranscriptionResult


def export_txt(result: TranscriptionResult) -> bytes:
    return result.text.encode("utf-8")


def export_json(result: TranscriptionResult) -> bytes:
    return json.dumps(result.model_dump(), ensure_ascii=False, indent=2).encode("utf-8")
