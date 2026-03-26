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
