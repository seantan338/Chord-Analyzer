import { describe, expect, it } from "vitest";
import { validateFile } from "./UploadPanel";

const limits = {
  max_upload_mb: 1,
  allowed_extensions: [".mp3", ".wav"],
  min_duration_seconds: 5,
  max_duration_seconds: 900,
};

function fakeFile(name: string, size: number): File {
  return { name, size } as File;
}

describe("validateFile", () => {
  it("accepts supported files", () =>
    expect(validateFile(fakeFile("a.MP3", 10), limits)).toBeNull());
  it("rejects other extensions", () => {
    expect(validateFile(fakeFile("a.exe", 10), limits)).toMatch(/Unsupported/);
  });
  it("rejects large files", () => {
    expect(validateFile(fakeFile("a.wav", 2 * 1024 * 1024), limits)).toMatch(/limit is 1 MB/);
  });
  it("rejects empty files", () =>
    expect(validateFile(fakeFile("a.wav", 0), limits)).toMatch(/empty/));
});
