"""Chord sheet model: sections -> lines -> bar cells, built from an analysis result.

Layout rules (shared by every text-based exporter):
  * one block per song section (or a single "Song" block when no sections exist),
  * four bars per line, chords inside a bar separated by spaces,
  * leading/trailing bars without chords are dropped; "N.C." marks silent bars inside.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.music.chords import NO_CHORD
from app.schemas.analysis import AnalysisResult, Bar

ChordMode = Literal["original", "beginner"]

BARS_PER_LINE = 4
NO_CHORD_LABEL = "N.C."


@dataclass(frozen=True)
class SheetSection:
    name: str
    start: float
    lines: list[list[str]]


@dataclass(frozen=True)
class ChordSheet:
    title: str
    key: str
    bpm: float
    time_signature: str
    mode: ChordMode
    notes: list[str] = field(default_factory=list)
    sections: list[SheetSection] = field(default_factory=list)


def bar_cell(bar: Bar, mode: ChordMode) -> str:
    names: list[str] = []
    for chord in bar.chords:
        name = chord.simplified if mode == "beginner" else chord.chord
        name = NO_CHORD_LABEL if name == NO_CHORD else name
        if not names or names[-1] != name:
            names.append(name)
    return " ".join(names) or NO_CHORD_LABEL


def _has_chord(bar: Bar) -> bool:
    return any(c.chord != NO_CHORD for c in bar.chords)


def _trim_silence(bars: list[Bar]) -> list[Bar]:
    voiced = [i for i, bar in enumerate(bars) if _has_chord(bar)]
    return bars[voiced[0] : voiced[-1] + 1] if voiced else []


def _title(filename: str) -> str:
    stem, dot, _ = filename.rpartition(".")
    return stem if dot and stem else filename


def build_sheet(result: AnalysisResult, mode: ChordMode = "original") -> ChordSheet:
    bars = _trim_silence(result.bars)
    blocks: list[tuple[str, float, list[Bar]]] = []
    if result.sections:
        for section in result.sections:
            members = [b for b in bars if section.bar_start <= b.index <= section.bar_end]
            if members:
                blocks.append((section.name, members[0].start, members))
    elif bars:
        blocks.append(("Song", bars[0].start, bars))

    sections = [
        SheetSection(
            name=name,
            start=start,
            lines=[
                [bar_cell(b, mode) for b in members[i : i + BARS_PER_LINE]]
                for i in range(0, len(members), BARS_PER_LINE)
            ],
        )
        for name, start, members in blocks
    ]

    notes: list[str] = []
    if result.view.semitones:
        sign = "+" if result.view.semitones > 0 else ""
        notes.append(f"Transposed {sign}{result.view.semitones} from {result.view.original_key}")
    if result.capo_suggestions:
        best = result.capo_suggestions[0]
        notes.append(f"Guitar: capo {best.capo}, play {best.play_key} shapes")
    if mode == "beginner":
        notes.append("Beginner chords (simplified)")

    return ChordSheet(
        title=_title(result.metadata.filename),
        key=result.music.key,
        bpm=result.music.bpm,
        time_signature=result.music.time_signature,
        mode=mode,
        notes=notes,
        sections=sections,
    )
