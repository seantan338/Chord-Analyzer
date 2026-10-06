"""Compact waveform overview for the UI (peak envelope, 0..1)."""

from __future__ import annotations

import numpy as np

WAVEFORM_POINTS = 1000


def waveform_peaks(samples: np.ndarray, n_points: int = WAVEFORM_POINTS) -> list[float]:
    if samples.size == 0:
        return []
    n_points = min(n_points, samples.size)
    edges = np.linspace(0, samples.size, n_points + 1).astype(int)
    peaks = np.maximum.reduceat(np.abs(samples), edges[:-1])
    top = float(peaks.max()) or 1.0
    return [round(float(v), 3) for v in peaks / top]
