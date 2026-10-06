"""FFmpeg-based decoding: any supported container -> mono float WAV at a fixed rate.

Uploaded files are never executed or passed through a shell. FFmpeg is invoked with an
argument list, a forced demuxer and a file-only protocol whitelist.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from app.audio.formats import AudioFormat
from app.audio.types import SAMPLE_RATE, AudioSignal
from app.core.errors import CorruptedAudioError, DependencyMissingError, FFmpegError

logger = logging.getLogger(__name__)

PROBE_TIMEOUT_SECONDS = 30
CONVERT_TIMEOUT_SECONDS = 180


@dataclass(frozen=True)
class ProbeInfo:
    duration: float | None
    codec: str | None
    sample_rate: int | None
    channels: int | None


def require_binary(path: str) -> str:
    resolved = shutil.which(path)
    if resolved is None:
        raise DependencyMissingError()
    return resolved


def probe(path: Path, fmt: AudioFormat, ffprobe_path: str = "ffprobe") -> ProbeInfo:
    cmd = [
        require_binary(ffprobe_path),
        "-v", "error",
        "-protocol_whitelist", "file",
        "-f", fmt.demuxer,
        "-show_entries", "format=duration:stream=codec_type,codec_name,sample_rate,channels",
        "-of", "json",
        str(path),
    ]  # fmt: skip
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=PROBE_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired as exc:
        raise CorruptedAudioError() from exc
    if proc.returncode != 0:
        logger.info("ffprobe rejected file: %s", proc.stderr.decode(errors="replace")[:500])
        raise CorruptedAudioError()
    try:
        data = json.loads(proc.stdout or b"{}")
    except json.JSONDecodeError as exc:
        raise CorruptedAudioError() from exc
    audio_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    if not audio_streams:
        raise CorruptedAudioError("This file does not contain an audio track.")
    stream = audio_streams[0]
    raw_duration = data.get("format", {}).get("duration")
    return ProbeInfo(
        duration=float(raw_duration) if raw_duration not in (None, "N/A") else None,
        codec=stream.get("codec_name"),
        sample_rate=int(stream["sample_rate"]) if stream.get("sample_rate") else None,
        channels=stream.get("channels"),
    )


def convert_to_wav(
    source: Path,
    fmt: AudioFormat,
    target: Path,
    *,
    sample_rate: int = SAMPLE_RATE,
    max_duration: float,
    ffmpeg_path: str = "ffmpeg",
) -> None:
    cmd = [
        require_binary(ffmpeg_path),
        "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-protocol_whitelist", "file",
        "-f", fmt.demuxer,
        "-i", str(source),
        "-map", "0:a:0", "-vn", "-sn", "-dn",
        "-ac", "1",
        "-ar", str(sample_rate),
        # read one second past the limit so "too long" can be detected reliably
        "-t", f"{max_duration + 1:.0f}",
        "-c:a", "pcm_f32le",
        "-f", "wav",
        str(target),
    ]  # fmt: skip
    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=CONVERT_TIMEOUT_SECONDS, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError("Converting this audio took too long.") from exc
    if proc.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        logger.warning(
            "ffmpeg failed (%s): %s", proc.returncode, proc.stderr.decode(errors="replace")[:500]
        )
        raise FFmpegError()


def load_wav(path: Path) -> AudioSignal:
    try:
        samples, sr = sf.read(str(path), dtype="float32", always_2d=False)
    except (RuntimeError, sf.LibsndfileError) as exc:
        raise CorruptedAudioError() from exc
    if samples.ndim > 1:
        samples = samples.mean(axis=1).astype(np.float32)
    samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
    return AudioSignal(samples=np.ascontiguousarray(samples, dtype=np.float32), sample_rate=int(sr))
