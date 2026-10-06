"""Derived views of a stored analysis (transposition), computed on read.

The stored result is always the original key. A view re-spells every chord for the new
key and recomputes capo suggestions, so clients never implement music theory themselves.
"""

from __future__ import annotations

from app.core.errors import InvalidRequestError
from app.music.keys import Key, KeyParseError, parse_key, semitones_between
from app.music.transpose import normalize_semitones, transpose_symbol
from app.schemas.analysis import AnalysisResult, KeyCandidate, ViewInfo
from app.services.result_builder import capo_fields


def resolve_shift(original: Key, semitones: int, target_key: str | None) -> int:
    if target_key:
        try:
            target = parse_key(target_key)
        except KeyParseError as exc:
            raise InvalidRequestError(f"Unknown key: {target_key!r}.") from exc
        if target.mode is not original.mode:
            raise InvalidRequestError(
                f"Target key must be a {original.mode.value} key (the song is in {original.name})."
            )
        return semitones_between(original, target)
    return normalize_semitones(semitones)


def transpose_result(
    result: AnalysisResult, *, semitones: int = 0, target_key: str | None = None
) -> AnalysisResult:
    original = parse_key(result.view.original_key)
    shift = resolve_shift(original, semitones, target_key)
    if shift == 0:
        return result
    key = original.transposed(shift)

    def t(symbol: str) -> str:
        return transpose_symbol(symbol, shift, key)

    chords = [
        c.model_copy(update={"chord": t(c.chord), "simplified": t(c.simplified)})
        for c in result.chords
    ]
    beginner = [c.model_copy(update={"chord": t(c.chord)}) for c in result.beginner_chords]
    bars = [
        bar.model_copy(
            update={
                "chords": [
                    bc.model_copy(update={"chord": t(bc.chord), "simplified": t(bc.simplified)})
                    for bc in bar.chords
                ]
            }
        )
        for bar in result.bars
    ]
    alternatives = [
        KeyCandidate(key=parse_key(c.key).transposed(shift).name, score=c.score)
        for c in result.music.key_alternatives
    ]
    capo, capo_note = capo_fields(key, chords)
    return result.model_copy(
        update={
            "music": result.music.model_copy(
                update={"key": key.name, "key_alternatives": alternatives}
            ),
            "chords": chords,
            "beginner_chords": beginner,
            "bars": bars,
            "capo_suggestions": capo,
            "capo_note": capo_note,
            "view": ViewInfo(semitones=shift, original_key=original.name),
        }
    )
