"""Tuning-corrected treble and bass chroma, aggregated on the beat grid.

Harmonic/percussive separation is done in the constant-Q domain: sustained (harmonic)
energy is smooth along time, transients (drums) are smooth along frequency. A soft
Wiener-style mask keeps the harmonic part. This is ~8x cheaper than STFT-domain HPSS
because the CQT has far fewer bins, and chroma is all we need the harmonic part for.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.audio.types import BeatGrid, ChromaFeatures, FloatArray

TREBLE_BINS_PER_OCTAVE = 36
TREBLE_OCTAVES = 5  # C3 .. C8
BASS_BINS_PER_OCTAVE = 24  # Hann nulls fall exactly on neighbouring semitones
BASS_OCTAVES = 2  # C1 .. B2 (24 bins/octave: ~0.4 s windows around E2)
LOG_COMPRESSION = 100.0
HARMONIC_KERNEL_FRAMES = 17  # ~0.4 s along time
PERCUSSIVE_KERNEL_TREBLE = 9  # 1/4 octave along frequency at 36 bins/octave
PERCUSSIVE_KERNEL_BASS = 7
BASS_LEAKAGE_FIFTH = 0.35
BASS_LEAKAGE_OCTAVE = 0.3


def _fold(cqt_mag: FloatArray, bins_per_octave: int, fmin: float) -> FloatArray:
    import librosa

    mapping = librosa.filters.cq_to_chroma(
        cqt_mag.shape[0], bins_per_octave=bins_per_octave, n_chroma=12, fmin=fmin
    )
    return np.asarray(mapping @ cqt_mag, dtype=np.float64)


def _l2_normalize(matrix: FloatArray) -> FloatArray:
    norms = np.linalg.norm(matrix, axis=0, keepdims=True)
    return np.asarray(matrix / np.maximum(norms, 1e-9), dtype=np.float64)


def _max_normalize(matrix: FloatArray) -> FloatArray:
    peaks = np.max(matrix, axis=0, keepdims=True)
    return np.asarray(matrix / np.maximum(peaks, 1e-9), dtype=np.float64)


@dataclass(frozen=True)
class FrameFeatures:
    treble: FloatArray  # (12, n_frames) log-compressed harmonic chroma, C3..C8
    bass: FloatArray  # (12, n_frames) log-compressed harmonic chroma, C1..B2
    rms: FloatArray  # (n_frames,) harmonic energy per frame
    tuning: float  # semitone fraction relative to A440
    harmonic_ratio: float  # share of CQT energy classified as harmonic


def harmonic_mask(cqt_mag: FloatArray, freq_kernel: int) -> FloatArray:
    from scipy.ndimage import median_filter

    harmonic = median_filter(cqt_mag, size=(1, HARMONIC_KERNEL_FRAMES))
    percussive = median_filter(cqt_mag, size=(freq_kernel, 1))
    h2, p2 = np.square(harmonic), np.square(percussive)
    return np.asarray(h2 / np.maximum(h2 + p2, 1e-12), dtype=np.float64)


def frame_chroma(samples: np.ndarray, sr: int, hop: int) -> FrameFeatures:
    """Frame-level harmonic treble/bass chroma and loudness."""
    import librosa

    # Tuning in fractions of a semitone; recordings are often a few cents off A440.
    tuning = float(librosa.estimate_tuning(y=samples, sr=sr, bins_per_octave=12))
    treble_fmin = float(librosa.note_to_hz("C3"))
    bass_fmin = float(librosa.note_to_hz("C1"))

    treble_cqt = np.abs(
        librosa.cqt(
            samples,
            sr=sr,
            hop_length=hop,
            fmin=treble_fmin,
            n_bins=TREBLE_BINS_PER_OCTAVE * TREBLE_OCTAVES,
            bins_per_octave=TREBLE_BINS_PER_OCTAVE,
            tuning=tuning * TREBLE_BINS_PER_OCTAVE / 12,
        )
    )
    bass_cqt = np.abs(
        librosa.cqt(
            samples,
            sr=sr,
            hop_length=hop,
            fmin=bass_fmin,
            n_bins=BASS_BINS_PER_OCTAVE * BASS_OCTAVES,
            bins_per_octave=BASS_BINS_PER_OCTAVE,
            tuning=tuning * BASS_BINS_PER_OCTAVE / 12,
        )
    )
    total_energy = float(np.sum(np.square(treble_cqt))) or 1.0
    treble_cqt = treble_cqt * harmonic_mask(treble_cqt, PERCUSSIVE_KERNEL_TREBLE)
    bass_cqt = bass_cqt * harmonic_mask(bass_cqt, PERCUSSIVE_KERNEL_BASS)
    harmonic_ratio = float(np.sum(np.square(treble_cqt))) / total_energy

    scale = max(float(treble_cqt.max()), float(bass_cqt.max()), 1e-9)
    treble = _fold(
        np.log1p(LOG_COMPRESSION * treble_cqt / scale), TREBLE_BINS_PER_OCTAVE, treble_fmin
    )
    bass = _fold(np.log1p(LOG_COMPRESSION * bass_cqt / scale), BASS_BINS_PER_OCTAVE, bass_fmin)

    n_frames = min(treble.shape[1], bass.shape[1])
    energy = np.sqrt(np.mean(np.square(treble_cqt[:, :n_frames]), axis=0))
    return FrameFeatures(
        treble=treble[:, :n_frames],
        bass=bass[:, :n_frames],
        rms=np.asarray(energy, dtype=np.float64),
        tuning=tuning,
        harmonic_ratio=min(1.0, harmonic_ratio),
    )


def sync_to_grid(matrix: FloatArray, grid: BeatGrid, aggregate: str = "median") -> FloatArray:
    """Aggregate frame-level columns into grid intervals."""
    n_frames = matrix.shape[-1]
    out = np.zeros((*matrix.shape[:-1], grid.n_intervals), dtype=np.float64)
    reducer = np.median if aggregate == "median" else np.mean
    for i in range(grid.n_intervals):
        a = min(int(grid.frames[i]), n_frames - 1)
        b = max(a + 1, min(int(grid.frames[i + 1]), n_frames))
        out[..., i] = reducer(matrix[..., a:b], axis=-1)
    return out


def compensate_bass_leakage(
    treble: FloatArray, bass: FloatArray, fifth: float, octave: float
) -> FloatArray:
    """Remove the bass line's harmonics from the treble chroma.

    A bass B2 has strong harmonics at B3/B4 (octaves) and F#4 (3rd harmonic), which make
    G/B look like Bm. The bass pitch class is known from the bass chroma, so those pitch
    classes are attenuated in the treble before chord matching.
    """
    scale = np.max(treble, axis=0, keepdims=True)
    leakage = fifth * np.roll(bass, 7, axis=0) + octave * bass
    return np.asarray(np.maximum(treble - leakage * scale, 0.0), dtype=np.float64)


def beat_chroma(frames: FrameFeatures, grid: BeatGrid) -> ChromaFeatures:
    bass = _max_normalize(sync_to_grid(frames.bass, grid))
    treble = _l2_normalize(sync_to_grid(frames.treble, grid))
    treble = _l2_normalize(
        compensate_bass_leakage(treble, bass, BASS_LEAKAGE_FIFTH, BASS_LEAKAGE_OCTAVE)
    )
    return ChromaFeatures(
        treble=treble,
        bass=bass,
        energy=sync_to_grid(frames.rms[np.newaxis, :], grid)[0],
        interval_times=grid.times,
        frame_treble=frames.treble,
    )
