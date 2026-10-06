"use client";

import { Loader2, Minus, Plus, RotateCcw } from "lucide-react";
import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NO_CHORD } from "@/lib/chords";
import { formatShift, transpositionOptions } from "@/lib/keys";
import type { AnalysisResult, ChordMode } from "@/types/analysis";
import { CapoSuggestions } from "./CapoSuggestions";

function progression(result: AnalysisResult, mode: ChordMode, limit = 8): string[] {
  const out: string[] = [];
  for (const seg of result.chords) {
    const chord = mode === "beginner" ? seg.simplified : seg.chord;
    if (chord !== NO_CHORD && out[out.length - 1] !== chord) out.push(chord);
    if (out.length >= limit) break;
  }
  return out;
}

export function TransposeControls({
  semitones,
  loading,
  onTranspose,
}: {
  semitones: number;
  loading: boolean;
  onTranspose: (semitones: number) => void;
}) {
  return (
    <div className="inline-flex items-center gap-1" role="group" aria-label="Transpose">
      <Button
        variant="secondary"
        size="icon"
        aria-label="Down one semitone"
        onClick={() => onTranspose(semitones - 1)}
      >
        <Minus className="h-4 w-4" />
      </Button>
      <span className="w-16 text-center text-sm font-medium tabular-nums" aria-live="polite">
        {loading ? (
          <Loader2 className="mx-auto h-4 w-4 animate-spin" />
        ) : semitones > 0 ? (
          `+${semitones}`
        ) : (
          semitones
        )}
      </span>
      <Button
        variant="secondary"
        size="icon"
        aria-label="Up one semitone"
        onClick={() => onTranspose(semitones + 1)}
      >
        <Plus className="h-4 w-4" />
      </Button>
    </div>
  );
}

export function TransposePanel({
  original,
  result,
  mode,
  semitones,
  loading,
  error,
  onTranspose,
}: {
  original: AnalysisResult;
  result: AnalysisResult;
  mode: ChordMode;
  semitones: number;
  loading: boolean;
  error: string | null;
  onTranspose: (semitones: number) => void;
}) {
  const options = useMemo(() => transpositionOptions(original.music.key), [original.music.key]);
  const before = progression(original, mode);
  const after = progression(result, mode);

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Transpose</CardTitle>
          <p className="text-sm text-zinc-500">
            Change the key to suit your voice or instrument. Every chord is re-spelled for the new
            key.
          </p>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex flex-wrap items-center gap-4">
            <TransposeControls semitones={semitones} loading={loading} onTranspose={onTranspose} />
            <label className="flex items-center gap-2 text-sm">
              <span className="text-zinc-500">Target key</span>
              <select
                value={semitones}
                onChange={(e) => onTranspose(Number(e.target.value))}
                className="h-9 rounded-lg border border-zinc-300 bg-white px-2 dark:border-zinc-700 dark:bg-zinc-900"
              >
                {options.map((option) => (
                  <option key={option.shift} value={option.shift}>
                    {option.name}
                    {option.shift === 0 ? " (original)" : ""}
                  </option>
                ))}
              </select>
            </label>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onTranspose(0)}
              disabled={semitones === 0}
            >
              <RotateCcw className="h-4 w-4" /> Reset
            </Button>
          </div>
          {error && (
            <p role="alert" className="text-sm text-rose-600">
              {error}
            </p>
          )}
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-zinc-500">Original · {original.music.key}</dt>
              <dd className="mt-1 font-mono text-base">{before.join("  ")}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">
                Now · {result.music.key} · {formatShift(result.view.semitones)}
              </dt>
              <dd className="mt-1 font-mono text-base font-semibold">{after.join("  ")}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>
      <CapoSuggestions result={result} />
    </div>
  );
}
