from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.devtools.synth import SongSection, render_song
from app.main import create_app

SR = 22050

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg not installed",
)


def write_wav(path: Path, samples: np.ndarray, sr: int = SR) -> Path:
    sf.write(str(path), samples, sr, subtype="PCM_16")
    return path


def to_mp3(wav: Path) -> Path:
    mp3 = wav.with_suffix(".mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "128k", str(mp3)],
        check=True,
    )
    return mp3


@pytest.fixture(scope="session")
def song_samples() -> np.ndarray:
    """~31 s, 100 BPM, 4/4, C G Am F x 3 with a short silent lead-in."""
    return render_song(
        [SongSection(["C", "G", "Am", "F"] * 3)], bpm=100, beats_per_bar=4, lead_in_seconds=0.5
    )


@pytest.fixture(scope="session")
def song_wav(tmp_path_factory: pytest.TempPathFactory, song_samples: np.ndarray) -> Path:
    return write_wav(tmp_path_factory.mktemp("audio") / "song.wav", song_samples)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        data_dir=tmp_path / "data",
        job_runner="inline",
        rate_limit_analyze_per_minute=0,
        rate_limit_read_per_minute=0,
        max_upload_mb=5,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
