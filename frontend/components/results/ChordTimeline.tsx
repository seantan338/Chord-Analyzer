"use client";

import { memo, useEffect, useMemo, useRef } from "react";
import { usePlayer } from "@/components/player/player-context";
import { cn } from "@/lib/cn";
import { chordStyle, displayChord } from "@/lib/chords";
import { CONFIDENCE_LABEL } from "@/lib/confidence";
import { formatTime } from "@/lib/format";
import { useActiveIndex } from "@/lib/playback";
import type { TimelineSegment } from "@/types/analysis";
import { Waveform } from "./Waveform";

const PX_PER_SECOND = 28;
const MIN_BLOCK_PX = 52;

const ChordBlock = memo(function ChordBlock({
  segment,
  active,
  onSeek,
  blockRef,
}: {
  segment: TimelineSegment;
  active: boolean;
  onSeek: (time: number) => void;
  blockRef: (el: HTMLButtonElement | null) => void;
}) {
  const width = Math.max(MIN_BLOCK_PX, (segment.end - segment.start) * PX_PER_SECOND);
  const isLow = segment.confidence_level === "low";
  return (
    <button
      ref={blockRef}
      type="button"
      onClick={() => onSeek(segment.start)}
      aria-current={active ? "true" : undefined}
      title={`${displayChord(segment.chord)} at ${formatTime(segment.start)} · ${CONFIDENCE_LABEL[segment.confidence_level]}`}
      className={cn(
        "flex h-20 shrink-0 flex-col justify-between rounded-lg border-2 px-2 py-1.5 text-left text-zinc-900 transition-transform",
        isLow && "border-dashed",
        active ? "z-10 scale-105 shadow-lg ring-2 ring-violet-600 ring-offset-2 dark:ring-offset-zinc-950" : "hover:-translate-y-0.5",
      )}
      style={{ width, ...chordStyle(segment.chord) }}
    >
      <span className="truncate text-lg font-bold leading-tight">{displayChord(segment.chord)}</span>
      <span className="font-mono text-[11px] text-zinc-700">{formatTime(segment.start)}</span>
    </button>
  );
});

export function ChordTimeline({
  segments,
  duration,
  waveform,
}: {
  segments: TimelineSegment[];
  duration: number;
  waveform: number[];
}) {
  const { clock, seek, playing } = usePlayer();
  const starts = useMemo(() => segments.map((s) => s.start), [segments]);
  const active = useActiveIndex(clock, starts);
  const blockRefs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    if (!playing || active < 0) return;
    blockRefs.current[active]?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [active, playing]);

  return (
    <div className="space-y-4">
      <Waveform peaks={waveform} segments={segments} duration={duration} />
      <div className="overflow-x-auto pb-3" aria-label="Chord timeline">
        <div className="flex gap-1.5 p-2">
          {segments.map((segment, i) => (
            <ChordBlock
              key={`${segment.start}-${i}`}
              segment={segment}
              active={i === active}
              onSeek={seek}
              blockRef={(el) => {
                blockRefs.current[i] = el;
              }}
            />
          ))}
        </div>
      </div>
      <p className="text-xs text-zinc-500">
        Click a chord to jump there. Dashed outlines mark low-confidence chords.
      </p>
    </div>
  );
}
