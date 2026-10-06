import { describe, expect, it } from "vitest";
import { API_BASE_URL, exportUrl, viewQuery } from "./api";

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

describe("exportUrl", () => {
  it("builds export links", () => {
    expect(exportUrl("abc", "txt")).toBe(`${API_BASE_URL}/api/jobs/abc/export?format=txt`);
    expect(exportUrl("abc", "markdown", { semitones: -2, mode: "beginner", download: false })).toBe(
      `${API_BASE_URL}/api/jobs/abc/export?format=markdown&semitones=-2&mode=beginner&download=false`,
    );
  });
});
