"use client";

import { AlertTriangle } from "lucide-react";
import { useMemo } from "react";
import { usePlayer } from "@/components/player/player-context";
import { ConfidenceBadge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { chordStyle, chordUsage } from "@/lib/chords";
import { formatTime } from "@/lib/format";
import type { AnalysisResult, TimelineSegment } from "@/types/analysis";

export function OverviewPanel({
  result,
  segments,
  extra,
}: {
  result: AnalysisResult;
  segments: TimelineSegment[];
  extra?: React.ReactNode;
}) {
  const { seek } = usePlayer();
  const usage = useMemo(() => chordUsage(segments), [segments]);
  const firstStart = useMemo(() => {
    const map = new Map<string, number>();
    for (const s of segments) if (!map.has(s.chord)) map.set(s.chord, s.start);
    return map;
  }, [segments]);
  const { confidence } = result;

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Chords in this song</CardTitle>
          <p className="text-sm text-zinc-500">
            Most used first. Click a chord to hear where it first appears.
          </p>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {usage.map(({ chord, seconds }) => (
            <button
              key={chord}
              type="button"
              onClick={() => seek(firstStart.get(chord) ?? 0)}
              className="rounded-lg border-2 px-3 py-1.5 text-left text-zinc-900"
              style={chordStyle(chord)}
              title={`First at ${formatTime(firstStart.get(chord) ?? 0)}`}
            >
              <div className="text-lg font-bold leading-tight">{chord}</div>
              <div className="text-[11px] text-zinc-700">{Math.round(seconds)}s</div>
            </button>
          ))}
          {usage.length === 0 && <p className="text-sm text-zinc-500">No chords detected.</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Analysis confidence</CardTitle>
          <p className="text-sm text-zinc-500">
            Automatic detection is never perfect. Use your ears.
          </p>
        </CardHeader>
        <CardContent>
          <dl className="space-y-2 text-sm">
            {(
              [
                ["Key", confidence.key],
                ["Tempo", confidence.tempo],
                ["Time signature", confidence.time_signature],
                ["Chords", confidence.chords],
                ...(result.sections.length > 0
                  ? [["Structure", confidence.structure] as const]
                  : []),
              ] as const
            ).map(([label, score]) => (
              <div key={label} className="flex items-center justify-between gap-2">
                <dt className="text-zinc-600 dark:text-zinc-400">{label}</dt>
                <dd>
                  <ConfidenceBadge level={score.level} short />
                </dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      {extra}

      {result.warnings.length > 0 && (
        <Card className="border-amber-200 lg:col-span-3 dark:border-amber-900">
          <CardContent className="space-y-1 pt-5">
            {result.warnings.map((warning) => (
              <p
                key={warning}
                className="flex items-start gap-2 text-sm text-amber-800 dark:text-amber-300"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {warning}
              </p>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
