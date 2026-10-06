import { describe, expect, it } from "vitest";
import type { Bar, Section } from "@/types/analysis";
import { barLabel, buildSheet } from "./sheet";

function bar(index: number, ...chords: [string, string][]): Bar {
  return {
    index,
    start: index * 2,
    end: index * 2 + 2,
    chords: chords.map(([chord, simplified], i) => ({
      chord,
      simplified,
      beats: 2,
      start: index * 2 + i,
    })),
  };
}

const bars: Bar[] = [
  bar(0, ["N", "N"]),
  bar(1, ["C", "C"]),
  bar(2, ["G/B", "G"], ["G", "G"]),
  bar(3, ["Am7", "Am"]),
  bar(4, ["Fmaj7", "F"]),
  bar(5, ["C", "C"]),
  bar(6, ["N", "N"]),
];

describe("chord sheet", () => {
  it("labels bars and merges repeated beginner chords", () => {
    expect(barLabel(bars[2], "original")).toBe("G/B G");
    expect(barLabel(bars[2], "beginner")).toBe("G");
    expect(barLabel(bars[0], "original")).toBe("N.C.");
  });

  it("trims silent edges and wraps four bars per line", () => {
    const [block] = buildSheet(bars, [], "original");
    expect(block.name).toBe("Song");
    expect(block.lines.map((line) => line.map((b) => b.label))).toEqual([
      ["C", "G/B G", "Am7", "Fmaj7"],
      ["C"],
    ]);
  });

  it("groups bars by section", () => {
    const sections = [
      { name: "Intro", name_is_inferred: true, bar_start: 0, bar_end: 2 },
      { name: "Section A", name_is_inferred: false, bar_start: 3, bar_end: 6 },
    ] as Section[];
    const blocks = buildSheet(bars, sections, "beginner");
    expect(blocks.map((b) => b.name)).toEqual(["Intro", "Section A"]);
    expect(blocks[1].lines[0].map((b) => b.label)).toEqual(["Am", "F", "C"]);
  });
});
