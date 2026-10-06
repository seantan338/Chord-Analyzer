"use client";

import { Pause, Play, Upload } from "lucide-react";
import { useMemo, useRef } from "react";
import { Button } from "@/components/ui/button";
import { chordStyle, displayChord } from "@/lib/chords";
import { formatTime } from "@/lib/format";
import { useActiveIndex, usePlaybackTime } from "@/lib/playback";
import type { TimelineSegment } from "@/types/analysis";
import { usePlayer } from "./player-context";

function TimeReadout() {
  const { clock, duration } = usePlayer();
  const time = usePlaybackTime(clock);
  return (
    <span className="w-24 shrink-0 text-right font-mono text-xs tabular-nums text-zinc-500">
      {formatTime(time)} / {formatTime(duration)}
    </span>
  );
}

function SeekBar() {
  const { clock, duration, seek, hasAudio } = usePlayer();
  const time = usePlaybackTime(clock);
  return (
    <input
      type="range"
      aria-label="Seek"
      min={0}
      max={duration || 0}
      step={0.1}
      value={Math.min(time, duration || 0)}
      disabled={!hasAudio}
      onChange={(e) => seek(Number(e.target.value), false)}
      className="h-1.5 w-full cursor-pointer accent-violet-600 disabled:cursor-not-allowed"
    />
  );
}

function NowPlaying({ segments }: { segments: TimelineSegment[] }) {
  const { clock } = usePlayer();
  const starts = useMemo(() => segments.map((s) => s.start), [segments]);
  const index = useActiveIndex(clock, starts);
  const current = index >= 0 ? segments[index] : undefined;
  const next = segments.slice(index + 1).find((s) => s.chord !== current?.chord);
  return (
    <div className="flex items-center gap-3" aria-live="polite">
      <div
        className="flex h-12 min-w-16 items-center justify-center rounded-lg border-2 px-3 text-xl font-bold text-zinc-900"
        style={current ? chordStyle(current.chord) : undefined}
        title="Current chord"
      >
        {current ? displayChord(current.chord) : "–"}
      </div>
      <div className="hidden text-xs text-zinc-500 sm:block">
        <div>Next</div>
        <div className="text-base font-semibold text-zinc-700 dark:text-zinc-300">
          {next ? displayChord(next.chord) : "–"}
        </div>
      </div>
    </div>
  );
}

export function AudioPlayerBar({
  segments,
  onAttach,
}: {
  segments: TimelineSegment[];
  onAttach: (file: File) => void;
}) {
  const { hasAudio, playing, toggle } = usePlayer();
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="fixed inset-x-0 bottom-0 z-20 border-t border-zinc-200 bg-white/95 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/95">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
        <NowPlaying segments={segments} />
        {hasAudio ? (
          <Button
            size="icon"
            onClick={toggle}
            aria-label={playing ? "Pause" : "Play"}
            title="Play / pause (space)"
            className="rounded-full"
          >
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </Button>
        ) : (
          <>
            <Button variant="secondary" size="sm" onClick={() => inputRef.current?.click()}>
              <Upload className="h-4 w-4" /> Attach audio to play
            </Button>
            <input
              ref={inputRef}
              type="file"
              accept="audio/*"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) onAttach(file);
              }}
            />
          </>
        )}
        <div className="flex flex-1 items-center gap-3">
          <SeekBar />
          <TimeReadout />
        </div>
      </div>
    </div>
  );
}
