/**
 * Domain types for the frontend, derived from the backend OpenAPI contract.
 * Regenerate `api.generated.ts` with `npm run gen:api` after backend schema changes.
 */
import type { components } from "./api.generated";

type Schemas = components["schemas"];

export type AnalysisResult = Schemas["AnalysisResult"];
export type ChordSegment = Schemas["ChordSegment"];
export type SimpleChordSegment = Schemas["SimpleChordSegment"];
export type Bar = Schemas["Bar"];
export type BarChord = Schemas["BarChord"];
export type Section = Schemas["Section"];
export type CapoSuggestion = Schemas["CapoSuggestion"];
export type MusicInfo = Schemas["MusicInfo"];
export type JobState = Schemas["JobState"];
export type JobCreated = Schemas["JobCreated"];
export type StageInfo = Schemas["StageInfo"];
export type HealthResponse = Schemas["HealthResponse"];
export type ConfidenceLevel = ChordSegment["confidence_level"];

export type ChordMode = "original" | "beginner";

/** A timeline segment in either chord mode. */
export interface TimelineSegment {
  start: number;
  end: number;
  chord: string;
  confidence: number;
  confidence_level: ConfidenceLevel;
}
