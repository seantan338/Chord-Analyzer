"""Eagerly import heavy analysis modules (librosa loads lazily by default).

Imported once by the multiprocessing fork server so that every job process starts with
librosa, scipy and scikit-learn already in memory.
"""

from __future__ import annotations

import librosa
import scipy.ndimage
import scipy.sparse.csgraph

import app.services.worker  # noqa: F401

# Touch lazily-loaded librosa submodules so their imports happen here, not per job.
PRELOADED: tuple[object, ...] = (
    librosa.cqt,
    librosa.onset,
    librosa.beat,
    librosa.feature,
    librosa.segment,
    librosa.filters,
    scipy.ndimage.median_filter,
    scipy.sparse.csgraph.laplacian,
)
