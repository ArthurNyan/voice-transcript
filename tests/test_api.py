from pathlib import Path

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.services.audio import AudioProcessor


def test_index_page(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Русская транскрибация" in response.text


def test_transcribe_returns_result(client):
    response = client.post(
        "/api/transcribe",
        files={"file": ("sample.webm", b"fake-audio", "audio/webm")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "Привет мир"
    assert payload["language"] == "ru"
    assert payload["filename"] == "sample.webm"
    assert payload["segments"][0]["text"] == "Привет мир"


def test_export_txt_returns_text_file(client):
    payload = {
        "result": {
            "text": "Привет мир",
            "segments": [{"start": 0.0, "end": 1.2, "text": "Привет мир"}],
            "language": "ru",
            "duration_seconds": 1.2,
            "filename": "sample.webm",
        }
    }

    response = client.post("/api/export/txt", json=payload)

    assert response.status_code == 200
    assert response.text == "Привет мир"
    assert 'attachment; filename="transcript.txt"' == response.headers["content-disposition"]


def test_export_json_returns_structured_file(client):
    payload = {
        "result": {
            "text": "Привет мир",
            "segments": [{"start": 0.0, "end": 1.2, "text": "Привет мир"}],
            "language": "ru",
            "duration_seconds": 1.2,
            "filename": "sample.webm",
        }
    }

    response = client.post("/api/export/json", json=payload)

    assert response.status_code == 200
    assert response.json()["text"] == "Привет мир"
    assert response.json()["segments"][0]["start"] == 0.0


def test_create_job_returns_job_id(client):
    response = client.post(
        "/api/jobs",
        files={"file": ("sample.webm", b"fake-audio", "audio/webm")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"]
    assert payload["status"] in {"queued", "done"}


def test_get_job_status_returns_progress_and_result(client):
    create_response = client.post(
        "/api/jobs",
        files={"file": ("sample.webm", b"fake-audio", "audio/webm")},
    )
    job_id = create_response.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "done"
    assert payload["progress"] == 1.0
    assert payload["result"]["text"] == "Привет мир"


def test_get_job_result_returns_transcription(client):
    create_response = client.post(
        "/api/jobs",
        files={"file": ("sample.webm", b"fake-audio", "audio/webm")},
    )
    job_id = create_response.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}/result")

    assert response.status_code == 200
    assert response.json()["text"] == "Привет мир"


def test_list_jobs_returns_created_job(client):
    create_response = client.post(
        "/api/jobs",
        files={"file": ("sample.webm", b"fake-audio", "audio/webm")},
    )
    job_id = create_response.json()["job_id"]

    response = client.get("/api/jobs")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["job_id"] == job_id
    assert payload[0]["status"] == "done"


def test_delete_job_removes_it_from_store(client):
    create_response = client.post(
        "/api/jobs",
        files={"file": ("sample.webm", b"fake-audio", "audio/webm")},
    )
    job_id = create_response.json()["job_id"]

    delete_response = client.delete(f"/api/jobs/{job_id}")
    list_response = client.get("/api/jobs")

    assert delete_response.status_code == 200
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_clear_jobs_removes_all_jobs(client):
    client.post("/api/jobs", files={"file": ("first.webm", b"fake-audio", "audio/webm")})
    client.post("/api/jobs", files={"file": ("second.webm", b"fake-audio", "audio/webm")})

    clear_response = client.delete("/api/jobs")
    list_response = client.get("/api/jobs")

    assert clear_response.status_code == 200
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_voice_example_duration_limit():
    source_path = Path("voice-exemple.m4a")
    assert source_path.exists()

    processor = AudioProcessor(Settings(max_audio_duration_minutes=10))

    with pytest.raises(HTTPException) as exc_info:
        processor.validate_duration(source_path)

    assert exc_info.value.status_code == 400
    assert "Максимум: 10 минут" in exc_info.value.detail
