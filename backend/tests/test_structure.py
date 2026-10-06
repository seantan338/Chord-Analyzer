from __future__ import annotations

import pytest

from app.audio.pipeline import PipelineOptions, analyze_signal
from app.audio.structure import infer_names
from app.audio.types import AudioSignal
from app.devtools.synth import SongSection, render_song
from app.services.result_builder import build_result


def _spans(lengths: list[int]) -> list[tuple[int, int]]:
    spans, start = [], 1
    for length in lengths:
        spans.append((start, start + length - 1))
        start += length
    return spans


def test_names_for_a_typical_pop_form() -> None:
    letters = ["A", "B", "C", "B", "C", "D", "C", "A"]
    spans = _spans([4, 8, 8, 8, 8, 8, 8, 4])
    energy = [0.3, 0.6, 1.0, 0.6, 1.0, 0.7, 1.0, 0.3]
    names = [name for name, _ in infer_names(letters, spans, energy)]
    assert names == ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"]


def test_pre_chorus_needs_verse_before_and_chorus_after() -> None:
    letters = ["A", "B", "P", "C", "B", "P", "C"]
    spans = _spans([4, 8, 4, 8, 8, 4, 8])
    energy = [0.3, 0.6, 0.8, 1.0, 0.6, 0.8, 1.0]
    names = [name for name, _ in infer_names(letters, spans, energy)]
    assert names == ["Intro", "Verse", "Pre-Chorus", "Chorus", "Verse", "Pre-Chorus", "Chorus"]


def test_no_repetition_means_no_verse_or_chorus() -> None:
    letters = ["A", "B", "C", "D"]
    names = infer_names(letters, _spans([8, 8, 8, 8]), [0.5, 0.6, 0.7, 0.6])
    assert {name for name, _ in names} <= {"", "Intro", "Outro"}
    assert all(name not in ("Verse", "Chorus") for name, _ in names)


def test_weak_evidence_gets_lower_confidence() -> None:
    letters = ["A", "B", "A", "B"]
    names = infer_names(letters, _spans([8, 8, 8, 8]), [0.6, 0.62, 0.6, 0.62])
    assert all(conf < 0.5 for name, conf in names if name in ("Verse", "Chorus"))


@pytest.mark.slow
def test_structure_on_synthesized_pop_song() -> None:
    intro = SongSection(["C", "F"] * 2, timbre="pad", drums=False, gain=0.5)
    verse = SongSection(["C", "G", "Am", "F"] * 2, gain=0.7)
    chorus = SongSection(["F", "G", "C", "Am"] * 2, gain=1.0)
    bridge = SongSection(["Am", "Em", "F", "C", "Am", "Em", "G", "G"], timbre="pad", gain=0.8)
    outro = SongSection(["C", "F", "C", "C"], timbre="pad", drums=False, gain=0.5)
    form = [intro, verse, chorus, verse, chorus, bridge, chorus, outro]
    samples = render_song(form, 96, 4, lead_in_seconds=0.8)
    output = analyze_signal(AudioSignal(samples, 22050), PipelineOptions())
    result = build_result("x" * 32, output, filename="x.wav", file_size=1, analyzer_version="t")

    labels = [s.label for s in result.sections]
    assert labels == ["A", "B", "C", "B", "C", "D", "C", "A"]
    expected_starts = [1, 5, 13, 21, 29, 37, 45, 53]  # bar 0 is the pickup
    for section, bar in zip(result.sections[1:], expected_starts[1:], strict=True):
        assert abs(section.bar_start - bar) <= 1
    assert [s.name for s in result.sections if s.name_is_inferred][:3] == [
        "Intro",
        "Verse",
        "Chorus",
    ]
    assert result.confidence.structure.value > 0.5
    # sections tile the song without gaps
    for a, b in zip(result.sections, result.sections[1:], strict=False):
        assert a.bar_end + 1 == b.bar_start


def test_recurring_quiet_section_is_not_an_intro() -> None:
    letters = ["A", "B", "A", "B", "A", "B", "A", "B"]
    names = infer_names(letters, _spans([8] * 8), [0.5, 1.0] * 4)
    assert names[0][0] == "Verse"
    assert all(name != "Intro" for name, _ in names)


def test_sub_phrase_fragments_are_merged() -> None:
    from app.audio.structure import merge_fragments

    # chorus split by clustering into 6 + 2 bars, three times
    runs = [[0, 0, 7], [1, 8, 13], [2, 14, 15], [0, 16, 23], [1, 24, 29], [2, 30, 31]]
    assert merge_fragments(runs) == [[0, 0, 7], [1, 8, 15], [0, 16, 23], [1, 24, 31]]
    # a 4-bar pre-chorus always before an 8-bar chorus stays separate
    runs = [[0, 0, 7], [1, 8, 11], [2, 12, 19], [0, 20, 27], [1, 28, 31], [2, 32, 39]]
    assert merge_fragments(runs) == runs
