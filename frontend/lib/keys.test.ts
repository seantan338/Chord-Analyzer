import { describe, expect, it } from "vitest";
import { formatShift, isMinorKey, keyName, normalizeShift, transpositionOptions } from "./keys";

describe("keys", () => {
  it("normalizes shifts into [-5, 6]", () => {
    expect([0, 2, 7, 11, -7, 12, -1].map(normalizeShift)).toEqual([0, 2, -5, -1, 5, 0, -1]);
  });
  it("names keys canonically", () => {
    expect(keyName(3, false)).toBe("Eb Major");
    expect(keyName(8, true)).toBe("G# Minor");
    expect(keyName(-1, false)).toBe("B Major");
  });
  it("lists transposition targets in the same mode", () => {
    const options = transpositionOptions("C Major");
    expect(options).toHaveLength(12);
    expect(options.find((o) => o.shift === 0)?.name).toBe("C Major");
    expect(options.find((o) => o.shift === 2)?.name).toBe("D Major");
    expect(options.find((o) => o.shift === -3)?.name).toBe("A Major");
    expect(transpositionOptions("A Minor").find((o) => o.shift === 3)?.name).toBe("C Minor");
    expect(isMinorKey("F# Minor")).toBe(true);
  });
  it("describes shifts", () => {
    expect(formatShift(0)).toBe("Original key");
    expect(formatShift(1)).toBe("+1 semitone");
    expect(formatShift(-2)).toBe("-2 semitones");
  });
});
