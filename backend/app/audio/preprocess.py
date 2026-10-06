"""Signal validation and normalisation."""

from __future__ import annotations

import numpy as np

from app.audio.types import AudioSignal
from app.core.errors import AudioTooLongError, AudioTooShortError, SilentAudioError

SILENCE_PEAK = 1e-3
SILENCE_RMS_DB = -55.0


def validate_signal(signal: AudioSignal, min_duration: float, max_duration: float) -> None:
    duration = signal.duration
    if duration < min_duration:
        raise AudioTooShortError(
            f"This audio is too short to analyze ({duration:.1f}s). "
            f"Please upload at least {min_duration:.0f} seconds."
        )
    if duration > max_duration + 0.5:
        raise AudioTooLongError(
            f"This audio is longer than the {max_duration / 60:.0f}-minute limit."
        )
    samples = signal.samples
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64)))) if samples.size else 0.0
    rms_db = 20 * np.log10(max(rms, 1e-12))
    if peak < SILENCE_PEAK or rms_db < SILENCE_RMS_DB:
        raise SilentAudioError()


def normalize(signal: AudioSignal, headroom: float = 0.95) -> AudioSignal:
    peak = float(np.max(np.abs(signal.samples)))
    if peak <= 0:
        return signal
    scaled = (signal.samples * (headroom / peak)).astype(np.float32)
    return AudioSignal(samples=scaled, sample_rate=signal.sample_rate)
