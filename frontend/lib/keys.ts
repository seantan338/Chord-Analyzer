import { chordRoot } from "./chords";

// Canonical key names, matching the API (app/music/keys.py). Used only to label the
// target-key picker; all chord spelling happens server-side.
const MAJOR_TONICS = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];
const MINOR_TONICS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"];

/** Map any shift to the equivalent one in [-5, +6]. */
export function normalizeShift(semitones: number): number {
  const shift = ((semitones % 12) + 12) % 12;
  return shift > 6 ? shift - 12 : shift;
}

export function isMinorKey(keyName: string): boolean {
  return /minor$/i.test(keyName.trim());
}

export function keyTonic(keyName: string): number {
  return chordRoot(keyName.trim()) ?? 0;
}

export function keyName(tonic: number, minor: boolean): string {
  const names = minor ? MINOR_TONICS : MAJOR_TONICS;
  return `${names[((tonic % 12) + 12) % 12]} ${minor ? "Minor" : "Major"}`;
}

export interface KeyOption {
  shift: number;
  name: string;
}

/** The 12 keys reachable by transposition, ordered from -5 to +6 semitones. */
export function transpositionOptions(originalKey: string): KeyOption[] {
  const tonic = keyTonic(originalKey);
  const minor = isMinorKey(originalKey);
  return Array.from({ length: 12 }, (_, i) => i - 5).map((shift) => ({
    shift,
    name: keyName(tonic + shift, minor),
  }));
}

export function formatShift(semitones: number): string {
  if (semitones === 0) return "Original key";
  return `${semitones > 0 ? "+" : ""}${semitones} semitone${Math.abs(semitones) === 1 ? "" : "s"}`;
}
