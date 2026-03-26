import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.skipif(not Path("voice-exemple.m4a").exists(), reason="voice-exemple.m4a is required")
def test_real_audio_short_fragment_transcribes(tmp_path: Path):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is required")

    sample_path = tmp_path / "sample-15s.wav"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        "voice-exemple.m4a",
        "-t",
        "15",
        str(sample_path),
    ]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0, process.stderr

    client = TestClient(app)
    with sample_path.open("rb") as handle:
        response = client.post(
            "/api/transcribe",
            files={"file": ("sample-15s.wav", handle, "audio/wav")},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["language"] == "ru"
    assert payload["duration_seconds"] > 0
    assert payload["text"]
