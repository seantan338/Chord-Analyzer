import { describe, expect, it } from "vitest";
import { viewQuery } from "./api";

describe("viewQuery", () => {
  it("is empty for the original view", () => {
    expect(viewQuery({})).toBe("");
    expect(viewQuery({ semitones: 0 })).toBe("");
  });
  it("encodes semitones", () => expect(viewQuery({ semitones: -2 })).toBe("?semitones=-2"));
  it("prefers a target key", () => {
    expect(viewQuery({ semitones: 3, targetKey: "F# Major" })).toBe("?target_key=F%23+Major");
  });
});
