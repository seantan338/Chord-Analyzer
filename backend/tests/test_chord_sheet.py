from __future__ import annotations

from app.exporters.chord_sheet import build_sheet
from app.services.result_view import transpose_result
from tests.factories import make_result, section

BARS = [
    [("N", "N")],
    [("C", "C")],
    [("G/B", "G"), ("G", "G")],
    [("Am7", "Am")],
    [("Fmaj7", "F")],
    [("C", "C")],
    [("N", "N")],
]


def test_sheet_without_sections() -> None:
    sheet = build_sheet(make_result(BARS))
    assert sheet.title == "My Song"
    assert [s.name for s in sheet.sections] == ["Song"]
    assert sheet.sections[0].lines == [["C", "G/B G", "Am7", "Fmaj7"], ["C"]]
    assert sheet.notes == []


def test_beginner_sheet_merges_simplified_chords() -> None:
    sheet = build_sheet(make_result(BARS), mode="beginner")
    assert sheet.sections[0].lines[0] == ["C", "G", "Am", "F"]
    assert "Beginner chords (simplified)" in sheet.notes


def test_sheet_sections_and_silence_inside() -> None:
    bars = [*BARS[:4], [("N", "N")], *BARS[4:]]
    result = make_result(
        bars, sections=[section("A", "Intro", 0, 2, inferred=True), section("B", "Section B", 3, 7)]
    )
    sheet = build_sheet(result)
    assert [s.name for s in sheet.sections] == ["Intro", "Section B"]
    assert sheet.sections[0].lines == [["C", "G/B G"]]
    assert sheet.sections[1].lines == [["Am7", "N.C.", "Fmaj7", "C"]]


def test_transposed_sheet_has_note_and_capo() -> None:
    result = transpose_result(make_result(BARS), target_key="Eb")
    sheet = build_sheet(result)
    assert sheet.key == "Eb Major"
    assert sheet.sections[0].lines[0] == ["Eb", "Bb/D Bb", "Cm7", "Abmaj7"]
    assert sheet.notes[0] == "Transposed +3 from C Major"
    assert sheet.notes[1].startswith("Guitar: capo")
