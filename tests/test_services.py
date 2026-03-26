from app.models import Segment, TranscriptionResult
from app.services.export import export_json, export_txt


def test_export_txt_serializes_plain_text():
    result = TranscriptionResult(
        text="Тест",
        segments=[Segment(start=0.0, end=0.5, text="Тест")],
        language="ru",
        duration_seconds=0.5,
        filename="audio.webm",
    )

    assert export_txt(result) == "Тест".encode("utf-8")


def test_export_json_serializes_result():
    result = TranscriptionResult(
        text="Тест",
        segments=[Segment(start=0.0, end=0.5, text="Тест")],
        language="ru",
        duration_seconds=0.5,
        filename="audio.webm",
    )

    payload = export_json(result).decode("utf-8")

    assert '"text": "Тест"' in payload
    assert '"language": "ru"' in payload
