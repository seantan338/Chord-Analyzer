"""Audio analysis pipeline orchestration.

    decode (FFmpeg) -> validate/normalise -> CQT + harmonic/percussive mask -> chroma
    -> onset/tempo/beats -> beat grid -> beat-synchronous chroma -> meter/downbeats
    -> key (profile) -> chord HMM -> key refinement -> structure

Each stage reports progress through ``on_stage``. The output is DSP-level data; turning
it into the public result schema happens in ``app.services.result_builder``.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.audio import (
    chord_detection,
    chroma,
    grid,
    key_detection,
    meter,
    preprocess,
    structure,
    tempo,
)
from app.audio.bars import interval_bar_numbers
from app.audio.chord_refine import refine_chords
from app.audio.chord_smoothing import bar_positions, smooth_chords
from app.audio.formats import AudioFormat
from app.audio.loader import convert_to_wav, load_wav, probe
from app.audio.types import (
    HOP_LENGTH,
    SAMPLE_RATE,
    AudioSignal,
    BeatGrid,
    DetectedChord,
    KeyEstimate,
    MeterEstimate,
    TempoEstimate,
)
from app.audio.waveform import waveform_peaks
from app.core.errors import InsufficientHarmonicContentError
from app.models.job import Stage
from app.music.keys import Key, Mode

logger = logging.getLogger(__name__)

StageCallback = Callable[[Stage], None]

MIN_HARMONIC_RATIO = 0.02
NO_CHORD_WARNING_RATIO = 0.5


@dataclass(frozen=True)
class PipelineOptions:
    min_duration: float = 5.0
    max_duration: float = 900.0
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    chord_vocabulary: str = "extended"


@dataclass
class PipelineOutput:
    duration: float
    sample_rate: int
    tempo: TempoEstimate
    meter: MeterEstimate
    grid: BeatGrid
    key: KeyEstimate
    chords: list[DetectedChord]
    harmonic_ratio: float
    tuning: float
    waveform: list[float]
    sections: list[structure.DetectedSection] = field(default_factory=list)
    structure_confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)


def _noop(_: Stage) -> None:
    return None


def decode(source: Path, fmt: AudioFormat, work_dir: Path, options: PipelineOptions) -> AudioSignal:
    probe(source, fmt, options.ffprobe_path)
    wav_path = work_dir / "decoded.wav"
    try:
        convert_to_wav(
            source,
            fmt,
            wav_path,
            max_duration=options.max_duration,
            ffmpeg_path=options.ffmpeg_path,
        )
        return load_wav(wav_path)
    finally:
        wav_path.unlink(missing_ok=True)


def analyze_file(
    source: Path,
    fmt: AudioFormat,
    work_dir: Path,
    options: PipelineOptions,
    on_stage: StageCallback = _noop,
) -> PipelineOutput:
    on_stage(Stage.CONVERTING)
    signal = decode(source, fmt, work_dir, options)
    preprocess.validate_signal(signal, options.min_duration, options.max_duration)
    signal = preprocess.normalize(signal)
    return analyze_signal(signal, options, on_stage)


def analyze_signal(
    signal: AudioSignal, options: PipelineOptions, on_stage: StageCallback = _noop
) -> PipelineOutput:
    sr, hop = signal.sample_rate, HOP_LENGTH
    if sr != SAMPLE_RATE:
        logger.warning("unexpected sample rate %s", sr)
    warnings: list[str] = []

    on_stage(Stage.HARMONIC_FEATURES)
    frames = chroma.frame_chroma(signal.samples, sr, hop)
    if frames.harmonic_ratio < MIN_HARMONIC_RATIO:
        raise InsufficientHarmonicContentError()

    on_stage(Stage.TEMPO)
    env = tempo.onset_envelope(signal.samples, sr, hop)
    tempo_est = tempo.estimate_tempo(env, sr, hop)
    beat_grid = grid.build_grid(tempo_est.beat_frames, len(env), sr / hop, signal.duration)
    features = chroma.beat_chroma(frames, beat_grid)
    meter_est = meter.estimate_meter(
        beat_grid, features, meter.low_frequency_onset(signal.samples, sr, hop)
    )
    if tempo_est.alternatives and tempo_est.confidence < 0.6:
        alts = ", ".join(f"{a:g}" for a in tempo_est.alternatives)
        warnings.append(f"Tempo could also be felt as {alts} BPM (half/double-time).")

    on_stage(Stage.KEY)
    profile_scores = key_detection.profile_scores(key_detection.pitch_class_profile(features))
    initial_key = key_detection.estimate_key(profile_scores)

    on_stage(Stage.CHORDS)
    scores = chord_detection.emission_scores(features)
    log_emit = chord_detection.log_emissions(scores)
    chords = smooth_chords(
        features,
        scores,
        log_emit,
        beat_grid,
        meter_est.beats_per_bar,
        meter_est.downbeat_phase,
        Key(initial_key.tonic, Mode(initial_key.mode)),
    )
    chords = _check_harmonic_content(chords, warnings)
    # Key estimation uses the stable triads; refinement only adds detail afterwards.
    durations: dict[tuple[int, str], float] = defaultdict(float)
    for c in chords:
        if c.root is not None:
            durations[(c.root, c.suffix)] += c.end - c.start
    sequence = [(c.root, c.suffix) for c in chords if c.root is not None]
    key_est = key_detection.estimate_key(profile_scores, durations, sequence)
    if options.chord_vocabulary == "extended":
        positions = bar_positions(beat_grid, meter_est.beats_per_bar, meter_est.downbeat_phase)
        chords = refine_chords(chords, features, positions)

    on_stage(Stage.STRUCTURE)
    sections, structure_confidence = _structure(signal, frames, beat_grid, meter_est)

    on_stage(Stage.FINALIZING)
    return PipelineOutput(
        duration=round(signal.duration, 3),
        sample_rate=sr,
        tempo=tempo_est,
        meter=meter_est,
        grid=beat_grid,
        key=key_est,
        chords=chords,
        harmonic_ratio=frames.harmonic_ratio,
        tuning=frames.tuning,
        waveform=waveform_peaks(signal.samples),
        sections=sections,
        structure_confidence=structure_confidence,
        warnings=warnings,
    )


def _structure(
    signal: AudioSignal, frames: chroma.FrameFeatures, beat_grid: BeatGrid, meter_est: MeterEstimate
) -> tuple[list[structure.DetectedSection], float]:
    import librosa

    sr, hop = signal.sample_rate, HOP_LENGTH
    mfcc = librosa.feature.mfcc(y=signal.samples, sr=sr, hop_length=hop, n_mfcc=13)[1:]
    rms = librosa.feature.rms(y=signal.samples, hop_length=hop)
    return structure.detect_structure(
        chroma=chroma.sync_to_grid(frames.treble, beat_grid),
        timbre=chroma.sync_to_grid(np.asarray(mfcc, dtype=np.float64), beat_grid),
        energy=chroma.sync_to_grid(np.asarray(rms, dtype=np.float64), beat_grid)[0],
        bar_numbers=interval_bar_numbers(beat_grid, meter_est),
    )


def _check_harmonic_content(
    chords: list[DetectedChord], warnings: list[str]
) -> list[DetectedChord]:
    total = sum(c.end - c.start for c in chords) or 1.0
    no_chord = sum(c.end - c.start for c in chords if c.root is None)
    if no_chord / total > 0.95:
        raise InsufficientHarmonicContentError()
    if no_chord / total > NO_CHORD_WARNING_RATIO:
        warnings.append("Large parts of this audio have no clear chords (speech, drums or noise?).")
    return chords
