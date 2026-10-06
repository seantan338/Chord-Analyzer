import type { CSSProperties } from "react";
import type {
  ChordMode,
  ChordSegment,
  SimpleChordSegment,
  TimelineSegment,
} from "@/types/analysis";

export const NO_CHORD = "N";

const LETTER_PC: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

/** Root pitch class of a chord symbol (presentation only; music theory lives in the API). */
export function chordRoot(symbol: string): number | null {
  const match = /^([A-G])([#b]?)/.exec(symbol);
  if (!match) return null;
  const offset = match[2] === "#" ? 1 : match[2] === "b" ? -1 : 0;
  return (LETTER_PC[match[1]] + offset + 12) % 12;
}

export function isMinorLike(symbol: string): boolean {
  const suffix = symbol.replace(/^[A-G][#b]?/, "");
  return /^(m(?!aj)|dim|min)/.test(suffix);
}

/** Stable colour per chord: hue by root (circle of fifths), darker for minor chords. */
export function chordColor(symbol: string): { background: string; border: string } {
  const root = chordRoot(symbol);
  if (root === null || symbol === NO_CHORD) {
    return { background: "hsl(240 5% 90%)", border: "hsl(240 5% 70%)" };
  }
  const fifthsIndex = (root * 7) % 12;
  const hue = Math.round(fifthsIndex * 30);
  const minor = isMinorLike(symbol);
  return {
    background: `hsl(${hue} ${minor ? 45 : 70}% ${minor ? 80 : 86}%)`,
    border: `hsl(${hue} ${minor ? 40 : 60}% ${minor ? 48 : 55}%)`,
  };
}

export function chordStyle(symbol: string): CSSProperties {
  const { background, border } = chordColor(symbol);
  return { background, borderColor: border };
}

/** Index of the segment containing time ``t`` (binary search), or -1. */
export function findSegmentIndex(starts: readonly number[], t: number): number {
  let lo = 0;
  let hi = starts.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (starts[mid] <= t) {
      found = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return found;
}

export function timelineSegments(
  chords: ChordSegment[],
  beginner: SimpleChordSegment[],
  mode: ChordMode,
): TimelineSegment[] {
  if (mode === "beginner") return beginner;
  return chords.map(({ start, end, chord, confidence, confidence_level }) => ({
    start,
    end,
    chord,
    confidence,
    confidence_level,
  }));
}

/** Distinct chords ordered by total duration (most used first), ignoring "N". */
export function chordUsage(segments: TimelineSegment[]): { chord: string; seconds: number }[] {
  const totals = new Map<string, number>();
  for (const seg of segments) {
    if (seg.chord === NO_CHORD) continue;
    totals.set(seg.chord, (totals.get(seg.chord) ?? 0) + (seg.end - seg.start));
  }
  return [...totals.entries()]
    .map(([chord, seconds]) => ({ chord, seconds }))
    .sort((a, b) => b.seconds - a.seconds);
}

export function displayChord(symbol: string): string {
  return symbol === NO_CHORD ? "–" : symbol;
}
