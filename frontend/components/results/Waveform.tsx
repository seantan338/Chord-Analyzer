"use client";

import { useEffect, useRef, useState, type MouseEvent } from "react";
import { usePlayer } from "@/components/player/player-context";
import { chordColor } from "@/lib/chords";
import { usePlaybackTime } from "@/lib/playback";
import type { TimelineSegment } from "@/types/analysis";

const HEIGHT = 96;

function Playhead({ duration }: { duration: number }) {
  const { clock } = usePlayer();
  const time = usePlaybackTime(clock);
  const left = duration > 0 ? Math.min(100, (time / duration) * 100) : 0;
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-y-0 w-0.5 bg-violet-600"
      style={{ left: `${left}%` }}
    />
  );
}

/** Waveform overview with colour-coded chord regions. Click anywhere to seek. */
export function Waveform({
  peaks,
  segments,
  duration,
}: {
  peaks: number[];
  segments: TimelineSegment[];
  duration: number;
}) {
  const { seek } = usePlayer();
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || width === 0 || duration <= 0) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = HEIGHT * ratio;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(ratio, ratio);
    ctx.clearRect(0, 0, width, HEIGHT);

    for (const seg of segments) {
      const x0 = (seg.start / duration) * width;
      const x1 = (seg.end / duration) * width;
      ctx.fillStyle = chordColor(seg.chord).background;
      ctx.fillRect(x0, 0, Math.max(1, x1 - x0), HEIGHT);
    }

    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    ctx.fillStyle = dark ? "rgba(24, 24, 27, 0.75)" : "rgba(39, 39, 42, 0.7)";
    const mid = HEIGHT / 2;
    for (let x = 0; x < width; x += 2) {
      const i = Math.min(peaks.length - 1, Math.floor((x / width) * peaks.length));
      const h = Math.max(1, (peaks[i] ?? 0) * (HEIGHT / 2 - 4));
      ctx.fillRect(x, mid - h, 1.2, h * 2);
    }
  }, [width, peaks, segments, duration]);

  function onClick(event: MouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    seek(((event.clientX - rect.left) / rect.width) * duration);
  }

  return (
    <div
      ref={containerRef}
      onClick={onClick}
      role="presentation"
      className="relative w-full cursor-pointer overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800"
      style={{ height: HEIGHT }}
      title="Click to jump to this position"
    >
      <canvas ref={canvasRef} style={{ width: "100%", height: HEIGHT }} />
      <Playhead duration={duration} />
    </div>
  );
}
