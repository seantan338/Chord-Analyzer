"""Public analysis result contract (v1).

This is the single source of truth for the result shape. The frontend's TypeScript
types are generated from the OpenAPI schema produced by these models
(``npm run gen:api`` in /frontend).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ConfidenceLevel = Literal["high", "medium", "low"]
SCHEMA_VERSION = "1.0"


class Metadata(BaseModel):
    filename: str
    duration: float = Field(description="Seconds")
    file_size: int = Field(description="Bytes")
    sample_rate: int
    tuning_offset_cents: float = Field(description="Detected deviation from A440, in cents")
    analyzed_at: datetime
    analyzer_version: str


class KeyCandidate(BaseModel):
    key: str
    score: float


class MusicInfo(BaseModel):
    key: str = Field(description='e.g. "G Major"')
    key_confidence: float
    key_confidence_level: ConfidenceLevel
    key_alternatives: list[KeyCandidate]
    bpm: float
    bpm_confidence: float
    bpm_confidence_level: ConfidenceLevel
    bpm_alternatives: list[float] = Field(description="Plausible half/double-time readings")
    time_signature: str = Field(description='"4/4" or "3/4"')
    time_signature_confidence: float
    time_signature_confidence_level: ConfidenceLevel


class Rhythm(BaseModel):
    beats: list[float] = Field(description="Beat times in seconds")
    downbeats: list[float] = Field(description="Bar start times in seconds")


class ChordSegment(BaseModel):
    start: float
    end: float
    chord: str = Field(description='Detailed chord, e.g. "G/B" or "N" for no chord')
    simplified: str = Field(description='Beginner-friendly triad, e.g. "G"')
    confidence: float
    confidence_level: ConfidenceLevel
    bar: int = Field(description="Bar index the segment starts in (0 = pickup)")
    beat: int = Field(description="1-based beat within that bar (0 = before first beat)")


class SimpleChordSegment(BaseModel):
    start: float
    end: float
    chord: str
    confidence: float
    confidence_level: ConfidenceLevel


class BarChord(BaseModel):
    chord: str
    simplified: str
    beats: int
    start: float


class Bar(BaseModel):
    index: int = Field(description="1-based bar number; 0 = pickup before the first downbeat")
    start: float
    end: float
    chords: list[BarChord]


class Section(BaseModel):
    id: str
    label: str = Field(description='Repetition label: "A", "B", ... (same label = similar music)')
    name: str = Field(description='Display name, e.g. "Section A", or "Chorus" when inferred')
    name_is_inferred: bool = Field(description="True when name comes from heuristics, not audio")
    name_confidence: float
    start: float
    end: float
    bar_start: int
    bar_end: int
    confidence: float
    confidence_level: ConfidenceLevel


class CapoSuggestion(BaseModel):
    capo: int
    play_key: str = Field(description="Key of the chord shapes you play with this capo")
    play_chords: list[str] = Field(description="Distinct chord shapes in order of appearance")
    playability: float = Field(description="Share of the song covered by easy open chords")


class OverallConfidence(BaseModel):
    key: float
    tempo: float
    time_signature: float
    chords: float
    structure: float


class ViewInfo(BaseModel):
    semitones: int = Field(description="Transposition applied to this view")
    original_key: str
    chord_mode: Literal["original", "beginner"] = "original"


class AnalysisResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    analysis_id: str
    metadata: Metadata
    music: MusicInfo
    rhythm: Rhythm
    sections: list[Section]
    bars: list[Bar]
    chords: list[ChordSegment]
    beginner_chords: list[SimpleChordSegment] = Field(
        description="Simplified chords with consecutive duplicates merged"
    )
    capo_suggestions: list[CapoSuggestion]
    capo_note: str
    waveform: list[float] = Field(description="Peak envelope (0..1) for drawing a waveform")
    confidence: OverallConfidence
    warnings: list[str]
    view: ViewInfo
