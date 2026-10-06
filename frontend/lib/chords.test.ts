import { describe, expect, it } from "vitest";
import type { ChordSegment, SimpleChordSegment } from "@/types/analysis";
import { chordRoot, chordUsage, findSegmentIndex, isMinorLike, timelineSegments } from "./chords";

function seg(start: number, end: number, chord: string, simplified = chord): ChordSegment {
  return {
    start,
    end,
    chord,
    simplified,
    confidence: 0.9,
    confidence_level: "high",
    bar: 1,
    beat: 1,
  };
}

describe("findSegmentIndex", () => {
  const starts = [0, 3.2, 6.4, 9.6];
  it.each([
    [-1, -1],
    [0, 0],
    [3.19, 0],
    [3.2, 1],
    [7, 2],
    [100, 3],
  ])("t=%s -> %s", (t, expected) => {
    expect(findSegmentIndex(starts, t)).toBe(expected);
  });
  it("handles empty lists", () => expect(findSegmentIndex([], 1)).toBe(-1));
});

describe("chord helpers", () => {
  it("finds roots", () => {
    expect(chordRoot("C")).toBe(0);
    expect(chordRoot("F#m7")).toBe(6);
    expect(chordRoot("Bb/D")).toBe(10);
    expect(chordRoot("N")).toBeNull();
  });
  it("detects minor-like chords", () => {
    expect(isMinorLike("Am7")).toBe(true);
    expect(isMinorLike("Bdim")).toBe(true);
    expect(isMinorLike("Cmaj7")).toBe(false);
    expect(isMinorLike("G/B")).toBe(false);
  });
  it("ranks chord usage and ignores N", () => {
    const usage = chordUsage([seg(0, 2, "N"), seg(2, 6, "C"), seg(6, 7, "G"), seg(7, 9, "C")]);
    expect(usage.map((u) => u.chord)).toEqual(["C", "G"]);
    expect(usage[0].seconds).toBe(6);
  });
  it("switches between original and beginner timelines", () => {
    const chords = [seg(0, 2, "G/B", "G"), seg(2, 4, "G", "G")];
    const beginner: SimpleChordSegment[] = [
      { start: 0, end: 4, chord: "G", confidence: 0.9, confidence_level: "high" },
    ];
    expect(timelineSegments(chords, beginner, "original").map((s) => s.chord)).toEqual(["G/B", "G"]);
    expect(timelineSegments(chords, beginner, "beginner")).toBe(beginner);
  });
});
