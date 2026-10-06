from __future__ import annotations

import json

import pytest

from app.core.errors import InvalidRequestError
from app.exporters.registry import get_format
from app.schemas.analysis import AnalysisResult
from tests.factories import make_result, section

BARS = [
    [("N", "N")],
    [("C", "C")],
    [("G/B", "G"), ("G", "G")],
    [("Am7", "Am")],
    [("Fmaj7", "F")],
    [("C", "C")],
]


def _result() -> AnalysisResult:
    return make_result(
        BARS, sections=[section("A", "Intro", 0, 2, inferred=True), section("B", "Section B", 3, 5)]
    )


def test_text_export() -> None:
    text = get_format("txt").render(_result(), "original")
    assert isinstance(text, str)
    lines = text.splitlines()
    assert lines[0] == "My Song"
    assert lines[1] == "Key: C Major | Tempo: 120 BPM | Time: 4/4"
    assert "[Intro] 0:02" in lines  # first chord, after the silent pickup
    assert "| C      | G/B G  |" in lines
    assert "| Am7    | Fmaj7  | C      |" in lines
    assert "may contain errors" in lines[-1]


def test_text_export_beginner() -> None:
    text = get_format("text").render(_result(), "beginner")
    assert "| Am     | F      | C      |" in str(text)
    assert "Beginner chords (simplified)" in str(text)


def test_markdown_export() -> None:
    md = str(get_format("md").render(_result(), "original"))
    assert md.startswith("# My Song\n")
    assert "| C Major | 120 BPM | 4/4 |" in md
    assert "## Intro `0:02`" in md
    assert "| 0:02 | C | high |" in md
    assert md.count("```text") == 2


def test_json_export_roundtrips() -> None:
    raw = str(get_format("json").render(_result(), "original"))
    data = json.loads(raw)
    assert AnalysisResult.model_validate(data).music.key == "C Major"


def test_unknown_format() -> None:
    with pytest.raises(InvalidRequestError):
        get_format("docx")
