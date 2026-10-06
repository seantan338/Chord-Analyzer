"""Hand-built analysis results for exporter / view tests (no DSP involved)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.music.keys import parse_key
from app.schemas.analysis import (
    AnalysisResult,
    Bar,
    BarChord,
    ChordSegment,
    ConfidenceScore,
    Metadata,
    MusicInfo,
    OverallConfidence,
    Rhythm,
    Section,
    ViewInfo,
)
from app.services.result_builder import capo_fields, merge_simplified

HIGH = ConfidenceScore(value=0.9, level="high")


def make_result(
    bar_chords: list[list[tuple[str, str]]],
    *,
    key: str = "C Major",
    sections: list[Section] | None = None,
    bar_seconds: float = 2.0,
) -> AnalysisResult:
    """``bar_chords``: per bar, a list of (chord, simplified); each chord gets 2 beats."""
    bars: list[Bar] = []
    segments: list[ChordSegment] = []
    for index, chords in enumerate(bar_chords):
        start = index * bar_seconds
        step = bar_seconds / max(1, len(chords))
        cells = []
        for i, (chord, simplified) in enumerate(chords):
            t0 = start + i * step
            cells.append(BarChord(chord=chord, simplified=simplified, beats=2, start=t0))
            if segments and segments[-1].chord == chord:
                segments[-1] = segments[-1].model_copy(update={"end": t0 + step})
            else:
                segments.append(
                    ChordSegment(
                        start=t0,
                        end=t0 + step,
                        chord=chord,
                        simplified=simplified,
                        confidence=0.9,
                        confidence_level="high",
                        bar=index,
                        beat=1 + 2 * i,
                    )
                )
        bars.append(Bar(index=index, start=start, end=start + bar_seconds, chords=cells))

    capo, note = capo_fields(parse_key(key), segments)
    duration = len(bar_chords) * bar_seconds
    return AnalysisResult(
        analysis_id="a" * 32,
        metadata=Metadata(
            filename="My Song.mp3",
            duration=duration,
            file_size=1234,
            sample_rate=22050,
            tuning_offset_cents=0.0,
            analyzed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            analyzer_version="test",
        ),
        music=MusicInfo(
            key=key,
            key_confidence=0.9,
            key_confidence_level="high",
            key_alternatives=[],
            bpm=120.0,
            bpm_confidence=0.9,
            bpm_confidence_level="high",
            bpm_alternatives=[],
            time_signature="4/4",
            time_signature_confidence=0.9,
            time_signature_confidence_level="high",
        ),
        rhythm=Rhythm(beats=[], downbeats=[b.start for b in bars]),
        sections=sections or [],
        bars=bars,
        chords=segments,
        beginner_chords=merge_simplified(segments),
        capo_suggestions=capo,
        capo_note=note,
        waveform=[0.5] * 10,
        confidence=OverallConfidence(
            key=HIGH, tempo=HIGH, time_signature=HIGH, chords=HIGH, structure=HIGH
        ),
        warnings=[],
        view=ViewInfo(semitones=0, original_key=key),
    )


def section(label: str, name: str, bar_start: int, bar_end: int, inferred: bool = False) -> Section:
    return Section(
        id=f"s{bar_start}",
        label=label,
        name=name,
        name_is_inferred=inferred,
        name_confidence=0.6 if inferred else 0.0,
        start=bar_start * 2.0,
        end=(bar_end + 1) * 2.0,
        bar_start=bar_start,
        bar_end=bar_end,
        confidence=0.7,
        confidence_level="medium",
    )
