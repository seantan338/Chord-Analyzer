import { describe, expect, it } from "vitest";
import { fileExtension, formatBpm, formatBytes, formatTime, songTitle } from "./format";

describe("formatTime", () => {
  it.each([
    [0, "0:00"],
    [4.9, "0:04"],
    [92, "1:32"],
    [3600, "60:00"],
    [Number.NaN, "0:00"],
    [-3, "0:00"],
  ])("%s -> %s", (input, expected) => {
    expect(formatTime(input)).toBe(expected);
  });
});

describe("misc formatting", () => {
  it("formats bytes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });
  it("formats bpm", () => expect(formatBpm(81.6)).toBe("82 BPM"));
  it("derives song titles and extensions", () => {
    expect(songTitle("My Song (live).mp3")).toBe("My Song (live)");
    expect(songTitle("noext")).toBe("noext");
    expect(fileExtension("A.MP3")).toBe(".mp3");
  });
});
