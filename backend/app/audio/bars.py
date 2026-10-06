"""Group beat-aligned chord segments into bars (musically meaningful units)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.audio.chord_smoothing import bar_positions
from app.audio.types import BeatGrid, DetectedChord, MeterEstimate


@dataclass(frozen=True)
class BarSlot:
    segment_index: int  # index into the chord segment list
    beats: int  # number of grid intervals covered inside this bar
    start: float


@dataclass(frozen=True)
class BarData:
    index: int  # 1-based; 0 = pickup / pre-roll before the first downbeat
    start: float
    end: float
    slots: list[BarSlot]


def segment_index_per_interval(chords: list[DetectedChord], n_intervals: int) -> np.ndarray:
    owner = np.zeros(n_intervals, dtype=np.int64)
    for i, segment in enumerate(chords):
        owner[segment.start_beat : segment.end_beat] = i
    return owner


def interval_bar_numbers(grid: BeatGrid, meter: MeterEstimate) -> np.ndarray:
    """Bar number for every grid interval (0 = pickup before the first downbeat)."""
    positions = bar_positions(grid, meter.beats_per_bar, meter.downbeat_phase)
    return np.cumsum(positions == 0)


def build_bars(grid: BeatGrid, meter: MeterEstimate, chords: list[DetectedChord]) -> list[BarData]:
    numbers = interval_bar_numbers(grid, meter)
    owner = segment_index_per_interval(chords, grid.n_intervals)
    bars: list[BarData] = []
    for number in np.unique(numbers):
        intervals = np.where(numbers == number)[0]
        start, end = int(intervals[0]), int(intervals[-1]) + 1
        slots: list[BarSlot] = []
        for interval in range(start, end):
            seg = int(owner[interval])
            if slots and slots[-1].segment_index == seg:
                last = slots[-1]
                slots[-1] = BarSlot(seg, last.beats + 1, last.start)
            else:
                slots.append(BarSlot(seg, 1, float(grid.times[interval])))
        bars.append(BarData(int(number), float(grid.times[start]), float(grid.times[end]), slots))
    return bars
