"use client";

import { memo, useMemo } from "react";
import { usePlayer } from "@/components/player/player-context";
import { cn } from "@/lib/cn";
import { formatBpm, formatTime, songTitle } from "@/lib/format";
import { useActiveIndex } from "@/lib/playback";
import { buildSheet, type SheetBar } from "@/lib/sheet";
import type { AnalysisResult, ChordMode } from "@/types/analysis";

const BarCell = memo(function BarCell({
  bar,
  active,
  onSeek,
}: {
  bar: SheetBar;
  active: boolean;
  onSeek: (time: number) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSeek(bar.start)}
      aria-current={active ? "true" : undefined}
      title={`Bar ${bar.index} · ${formatTime(bar.start)}`}
      className={cn(
        "min-h-12 border-l-2 border-zinc-400 px-3 py-2 text-left font-mono text-lg font-semibold transition-colors dark:border-zinc-600",
        active
          ? "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-100"
          : "hover:bg-zinc-100 dark:hover:bg-zinc-800",
      )}
    >
      {bar.label}
    </button>
  );
});

export function ChordSheetPanel({
  result,
  mode,
  actions,
}: {
  result: AnalysisResult;
  mode: ChordMode;
  actions?: React.ReactNode;
}) {
  const { clock, seek } = usePlayer();
  const blocks = useMemo(() => buildSheet(result.bars, result.sections, mode), [result, mode]);
  const starts = useMemo(
    () => blocks.flatMap((block) => block.lines.flatMap((line) => line.map((bar) => bar.start))),
    [blocks],
  );
  const activeIndex = useActiveIndex(clock, starts);
  const activeStart = activeIndex >= 0 ? starts[activeIndex] : -1;
  const { music, view, capo_suggestions: capo } = result;

  return (
    <article className="rounded-xl border border-zinc-200 bg-white p-5 sm:p-8 dark:border-zinc-800 dark:bg-zinc-900">
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-zinc-200 pb-4 dark:border-zinc-800">
        <div>
          <h2 className="text-2xl font-bold">{songTitle(result.metadata.filename)}</h2>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Key: <strong>{music.key}</strong> · Tempo: <strong>{formatBpm(music.bpm)}</strong> ·
            Time: <strong>{music.time_signature}</strong>
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            {view.semitones !== 0 && <>Transposed from {view.original_key} · </>}
            {capo.length > 0 && (
              <>
                Guitar: capo {capo[0].capo}, play {capo[0].play_key} shapes ·{" "}
              </>
            )}
            {mode === "beginner" ? "Beginner chords" : "Original chords"}
          </p>
        </div>
        {actions}
      </header>

      <div className="mt-6 space-y-6">
        {blocks.map((block) => (
          <section key={`${block.name}-${block.start}`}>
            <h3 className="mb-2 flex items-baseline gap-2 text-sm font-semibold uppercase tracking-wide text-violet-700 dark:text-violet-300">
              [{block.name}]
              <span className="font-mono text-xs font-normal normal-case text-zinc-500">
                {formatTime(block.start)}
              </span>
              {block.inferred && (
                <span
                  className="text-xs font-normal normal-case text-zinc-400"
                  title="Name inferred from repetition and energy"
                >
                  (estimated)
                </span>
              )}
            </h3>
            <div className="space-y-1">
              {block.lines.map((line) => (
                <div
                  key={line[0].start}
                  className="grid grid-cols-4 border-r-2 border-zinc-400 dark:border-zinc-600"
                >
                  {line.map((bar) => (
                    <BarCell
                      key={bar.start}
                      bar={bar}
                      active={bar.start === activeStart}
                      onSeek={seek}
                    />
                  ))}
                </div>
              ))}
            </div>
          </section>
        ))}
        {blocks.length === 0 && <p className="text-sm text-zinc-500">No chords detected.</p>}
      </div>
    </article>
  );
}
