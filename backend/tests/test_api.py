"""HTTP API tests (inline job runner, real FFmpeg + DSP)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.schemas.analysis import AnalysisResult
from tests.conftest import requires_ffmpeg, to_mp3, write_wav

pytestmark = requires_ffmpeg


def _upload(client: TestClient, path: Path, name: str | None = None, mime: str = "audio/mpeg"):  # type: ignore[no-untyped-def]
    with path.open("rb") as fh:
        return client.post("/api/analyze", files={"file": (name or path.name, fh, mime)})


def test_health(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["ffmpeg"] is True
    assert ".mp3" in body["limits"]["allowed_extensions"]


@pytest.mark.slow
def test_mp3_upload_end_to_end(
    client: TestClient, song_samples: np.ndarray, tmp_path: Path
) -> None:
    mp3 = to_mp3(write_wav(tmp_path / "My Song.wav", song_samples))
    response = _upload(client, mp3)
    assert response.status_code in (200, 202)
    job_id = response.json()["job_id"]

    status = client.get(f"/api/jobs/{job_id}").json()
    assert status["status"] == "completed"
    assert status["stage"] == "complete"
    assert all(stage["state"] == "done" for stage in status["stages"])
    assert status["summary"]["key"] == "C Major"

    result = client.get(f"/api/jobs/{job_id}/result").json()
    AnalysisResult.model_validate(result)  # contract check
    assert result["metadata"]["filename"] == "My Song.mp3"
    assert result["music"]["key"] == "C Major"
    assert abs(result["music"]["bpm"] - 100) < 2
    assert result["music"]["time_signature"] == "4/4"
    names = {c["chord"] for c in result["chords"]}
    assert {"C", "G", "Am", "F"} <= names
    for seg in result["chords"]:
        assert {"start", "end", "chord", "confidence"} <= seg.keys()
        assert seg["end"] > seg["start"]
    assert len(result["waveform"]) > 100
    assert any(len(bar["chords"]) == 1 and bar["index"] >= 1 for bar in result["bars"])

    # temp audio is deleted after analysis
    tmp_root = client.app.state.settings.temp_root  # type: ignore[attr-defined]
    assert not any(tmp_root.iterdir())


@pytest.mark.slow
def test_identical_upload_hits_cache(client: TestClient, song_wav: Path) -> None:
    first = _upload(client, song_wav, mime="audio/wav").json()
    second = _upload(client, song_wav, name="copy.wav", mime="audio/wav")
    body = second.json()
    assert second.status_code == 200
    assert body["cached"] is True
    assert body["job_id"] != first["job_id"]
    assert body["result"]["metadata"]["filename"] == "copy.wav"


def test_rejects_unsupported_extension(client: TestClient, tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("hello")
    response = _upload(client, path, mime="text/plain")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_format"


def test_rejects_disguised_file(client: TestClient, tmp_path: Path) -> None:
    path = tmp_path / "song.mp3"
    path.write_bytes(b"#EXTM3U\n#EXTINF:10,\nhttp://example.com/a.ts\n")
    response = _upload(client, path)
    assert response.status_code == 415


def test_corrupted_audio_fails_gracefully(client: TestClient, tmp_path: Path) -> None:
    path = tmp_path / "broken.wav"
    path.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x07" * 64)
    job_id = _upload(client, path, mime="audio/wav").json()["job_id"]
    status = client.get(f"/api/jobs/{job_id}").json()
    assert status["status"] == "failed"
    assert status["error"]["code"] in {"corrupted_audio", "conversion_failed"}
    assert "Traceback" not in status["error"]["message"]
    result = client.get(f"/api/jobs/{job_id}/result")
    assert result.status_code == 422


def test_silent_audio(client: TestClient, tmp_path: Path) -> None:
    path = write_wav(tmp_path / "silence.wav", np.zeros(22050 * 10, dtype=np.float32))
    job_id = _upload(client, path, mime="audio/wav").json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["error"]["code"] == "silent_audio"


def test_too_short_audio(client: TestClient, tmp_path: Path) -> None:
    t = np.arange(22050 * 2) / 22050
    path = write_wav(tmp_path / "short.wav", (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32))
    job_id = _upload(client, path, mime="audio/wav").json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["error"]["code"] == "audio_too_short"


def test_too_large_upload(client: TestClient, tmp_path: Path) -> None:
    path = tmp_path / "big.wav"
    path.write_bytes(b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * (7 * 1024 * 1024))
    response = _upload(client, path, mime="audio/wav")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_unknown_job(client: TestClient) -> None:
    assert client.get("/api/jobs/" + "0" * 32).status_code == 404
    assert client.get("/api/jobs/../../etc").status_code == 404
    assert client.get("/api/jobs/not-a-job/result").json()["error"]["code"] == "not_found"


def test_missing_file_field(client: TestClient) -> None:
    response = client.post("/api/analyze")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_api_key_required_when_configured(settings, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from app.main import create_app

    settings.api_key = "secret"
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/jobs/" + "0" * 32).status_code == 401
        ok = client.get("/api/jobs/" + "0" * 32, headers={"X-API-Key": "secret"})
        assert ok.status_code == 404
        assert client.get("/api/health").status_code == 200


def test_rate_limit(settings) -> None:  # type: ignore[no-untyped-def]
    from app.main import create_app

    settings.rate_limit_read_per_minute = 2
    with TestClient(create_app(settings)) as client:
        codes = [client.get("/api/jobs/" + "0" * 32).status_code for _ in range(4)]
    assert codes[:2] == [404, 404]
    assert codes[-1] == 429
