import type { Bar, ChordMode, Section } from "@/types/analysis";
import { NO_CHORD } from "./chords";

// Mirrors the layout rules of the API's chord sheet exporter (app/exporters/chord_sheet.py).
export const BARS_PER_LINE = 4;
export const NO_CHORD_LABEL = "N.C.";

export interface SheetBar {
  index: number;
  start: number;
  label: string;
}

export interface SheetBlock {
  name: string;
  inferred: boolean;
  start: number;
  lines: SheetBar[][];
}

export function barLabel(bar: Bar, mode: ChordMode): string {
  const names: string[] = [];
  for (const chord of bar.chords) {
    const raw = mode === "beginner" ? chord.simplified : chord.chord;
    const name = raw === NO_CHORD ? NO_CHORD_LABEL : raw;
    if (names[names.length - 1] !== name) names.push(name);
  }
  return names.join(" ") || NO_CHORD_LABEL;
}

function trimSilence(bars: Bar[]): Bar[] {
  const voiced = bars.flatMap((bar, i) =>
    bar.chords.some((c) => c.chord !== NO_CHORD) ? [i] : [],
  );
  return voiced.length ? bars.slice(voiced[0], voiced[voiced.length - 1] + 1) : [];
}

function toLines(bars: Bar[], mode: ChordMode): SheetBar[][] {
  const lines: SheetBar[][] = [];
  for (let i = 0; i < bars.length; i += BARS_PER_LINE) {
    lines.push(
      bars.slice(i, i + BARS_PER_LINE).map((bar) => ({
        index: bar.index,
        start: bar.start,
        label: barLabel(bar, mode),
      })),
    );
  }
  return lines;
}

export function buildSheet(bars: Bar[], sections: Section[], mode: ChordMode): SheetBlock[] {
  const voiced = trimSilence(bars);
  if (voiced.length === 0) return [];
  if (sections.length === 0) {
    return [
      { name: "Song", inferred: false, start: voiced[0].start, lines: toLines(voiced, mode) },
    ];
  }
  return sections.flatMap((section) => {
    const members = voiced.filter(
      (b) => b.index >= section.bar_start && b.index <= section.bar_end,
    );
    if (members.length === 0) return [];
    return [
      {
        name: section.name,
        inferred: section.name_is_inferred,
        start: members[0].start,
        lines: toLines(members, mode),
      },
    ];
  });
}
