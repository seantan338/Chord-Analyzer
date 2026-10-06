"""Turn DSP-level pipeline output into the public ``AnalysisResult`` contract."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from app.audio.bars import build_bars, interval_bar_numbers
from app.audio.chord_smoothing import bar_positions
from app.audio.confidence import confidence_level, duration_weighted_mean
from app.audio.pipeline import PipelineOutput
from app.audio.types import DetectedChord
from app.music.capo import suggest_capo
from app.music.chords import NO_CHORD, Chord
from app.music.keys import Key, Mode
from app.music.simplifier import simplify_symbol
from app.schemas.analysis import (
    AnalysisResult,
    Bar,
    BarChord,
    CapoSuggestion,
    ChordSegment,
    ConfidenceScore,
    KeyCandidate,
    Metadata,
    MusicInfo,
    OverallConfidence,
    Rhythm,
    Section,
    SimpleChordSegment,
    ViewInfo,
)


def _r(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


def score(value: float) -> ConfidenceScore:
    value = round(float(value), 2)
    return ConfidenceScore(value=value, level=confidence_level(value))


def chord_symbol(chord: DetectedChord, key: Key) -> str:
    if chord.root is None:
        return NO_CHORD
    return Chord(chord.root, chord.suffix, chord.bass).format(key=key)


def merge_simplified(segments: Sequence[ChordSegment]) -> list[SimpleChordSegment]:
    """Beginner timeline: consecutive segments with the same simplified chord are merged."""
    merged: list[SimpleChordSegment] = []
    weights: list[list[tuple[float, float]]] = []
    for seg in segments:
        duration = seg.end - seg.start
        if merged and merged[-1].chord == seg.simplified:
            merged[-1] = merged[-1].model_copy(update={"end": seg.end})
            weights[-1].append((seg.confidence, duration))
        else:
            merged.append(
                SimpleChordSegment(
                    start=seg.start,
                    end=seg.end,
                    chord=seg.simplified,
                    confidence=seg.confidence,
                    confidence_level=seg.confidence_level,
                )
            )
            weights.append([(seg.confidence, duration)])
    for i, pairs in enumerate(weights):
        conf = duration_weighted_mean([c for c, _ in pairs], [d for _, d in pairs])
        merged[i] = merged[i].model_copy(
            update={"confidence": conf, "confidence_level": confidence_level(conf)}
        )
    return merged


def capo_fields(key: Key, segments: Sequence[ChordSegment]) -> tuple[list[CapoSuggestion], str]:
    advice = suggest_capo(key, [(s.chord, s.end - s.start) for s in segments])
    suggestions = [
        CapoSuggestion(
            capo=o.capo,
            play_key=o.play_key.name,
            play_chords=o.play_chords,
            playability=o.playability,
        )
        for o in advice.options
    ]
    return suggestions, advice.note


def build_sections(output: PipelineOutput, bars: Sequence[Bar]) -> list[Section]:
    by_index = {bar.index: bar for bar in bars}
    sections: list[Section] = []
    for i, detected in enumerate(output.sections):
        first, last = by_index.get(detected.bar_start), by_index.get(detected.bar_end)
        if first is None or last is None:
            continue
        sections.append(
            Section(
                id=f"s{i + 1}",
                label=detected.label,
                name=detected.name,
                name_is_inferred=detected.name_is_inferred,
                name_confidence=detected.name_confidence,
                start=first.start,
                end=last.end,
                bar_start=detected.bar_start,
                bar_end=detected.bar_end,
                confidence=detected.confidence,
                confidence_level=confidence_level(detected.confidence),
            )
        )
    return sections


def build_result(
    analysis_id: str,
    output: PipelineOutput,
    *,
    filename: str,
    file_size: int,
    analyzer_version: str,
) -> AnalysisResult:
    key = Key(output.key.tonic, Mode(output.key.mode))
    grid, meter = output.grid, output.meter
    positions = bar_positions(grid, meter.beats_per_bar, meter.downbeat_phase)
    bar_numbers = interval_bar_numbers(grid, meter)

    segments: list[ChordSegment] = []
    for chord in output.chords:
        symbol = chord_symbol(chord, key)
        segments.append(
            ChordSegment(
                start=_r(chord.start),
                end=_r(chord.end),
                chord=symbol,
                simplified=simplify_symbol(symbol, key=key),
                confidence=chord.confidence,
                confidence_level=confidence_level(chord.confidence),
                bar=int(bar_numbers[chord.start_beat]),
                beat=int(positions[chord.start_beat]) + 1,
            )
        )

    bars = [
        Bar(
            index=bar.index,
            start=_r(bar.start),
            end=_r(bar.end),
            chords=[
                BarChord(
                    chord=segments[slot.segment_index].chord,
                    simplified=segments[slot.segment_index].simplified,
                    beats=slot.beats,
                    start=_r(slot.start),
                )
                for slot in bar.slots
            ],
        )
        for bar in build_bars(grid, meter, output.chords)
    ]
    sections = build_sections(output, bars)

    voiced = [s for s in segments if s.chord != NO_CHORD]
    chord_conf = duration_weighted_mean(
        [s.confidence for s in voiced], [s.end - s.start for s in voiced]
    )
    capo_suggestions, capo_note = capo_fields(key, segments)
    alternatives = [
        KeyCandidate(key=name, score=round(score, 3))
        for name, score in output.key.scores.items()
        if name != key.name
    ][:2]

    tempo = output.tempo
    return AnalysisResult(
        analysis_id=analysis_id,
        metadata=Metadata(
            filename=filename,
            duration=_r(output.duration, 2),
            file_size=file_size,
            sample_rate=output.sample_rate,
            tuning_offset_cents=round(output.tuning * 100, 1),
            analyzed_at=datetime.now(timezone.utc),
            analyzer_version=analyzer_version,
        ),
        music=MusicInfo(
            key=key.name,
            key_confidence=output.key.confidence,
            key_confidence_level=confidence_level(output.key.confidence),
            key_alternatives=alternatives,
            bpm=round(tempo.bpm, 1),
            bpm_confidence=tempo.confidence,
            bpm_confidence_level=confidence_level(tempo.confidence),
            bpm_alternatives=tempo.alternatives,
            time_signature=meter.time_signature,
            time_signature_confidence=meter.confidence,
            time_signature_confidence_level=confidence_level(meter.confidence),
        ),
        rhythm=Rhythm(
            beats=[_r(t) for t in grid.beat_times],
            downbeats=[_r(t) for t in grid.times[:-1][positions == 0]],
        ),
        sections=sections,
        bars=bars,
        chords=segments,
        beginner_chords=merge_simplified(segments),
        capo_suggestions=capo_suggestions,
        capo_note=capo_note,
        waveform=output.waveform,
        confidence=OverallConfidence(
            key=score(output.key.confidence),
            tempo=score(tempo.confidence),
            time_signature=score(meter.confidence),
            chords=score(chord_conf),
            structure=score(output.structure_confidence),
        ),
        warnings=list(output.warnings),
        view=ViewInfo(semitones=0, original_key=key.name),
    )
