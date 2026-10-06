"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { PlaybackClock } from "@/lib/playback";

interface PlayerContextValue {
  clock: PlaybackClock;
  hasAudio: boolean;
  playing: boolean;
  duration: number;
  /** Jump to ``time`` seconds; starts playback unless ``play`` is false. */
  seek: (time: number, play?: boolean) => void;
  toggle: () => void;
}

const PlayerContext = createContext<PlayerContextValue | null>(null);

function useObjectUrl(file: File | null): string | null {
  const url = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => {
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [url]);
  return url;
}

export function PlayerProvider({
  file,
  fallbackDuration,
  children,
}: {
  file: File | null;
  fallbackDuration: number;
  children: ReactNode;
}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [clock] = useState(() => new PlaybackClock());
  const [playing, setPlaying] = useState(false);
  const [mediaDuration, setMediaDuration] = useState<number | null>(null);
  const src = useObjectUrl(file);

  // Smooth time updates while playing (timeupdate only fires ~4x per second).
  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    const tick = () => {
      const audio = audioRef.current;
      if (audio) clock.setTime(audio.currentTime);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, clock]);

  const seek = useCallback(
    (time: number, play = true) => {
      const target = Math.max(0, time);
      clock.setTime(target);
      const audio = audioRef.current;
      if (!audio) return;
      audio.currentTime = target;
      if (play) audio.play().catch(() => setPlaying(false));
    },
    [clock],
  );

  const toggle = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) audio.play().catch(() => setPlaying(false));
    else audio.pause();
  }, []);

  // Space bar toggles playback (unless typing in a form control).
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      if (event.code !== "Space" || tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if (tag === "BUTTON") return;
      event.preventDefault();
      toggle();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle]);

  const value = useMemo<PlayerContextValue>(
    () => ({
      clock,
      hasAudio: src !== null,
      playing,
      duration: mediaDuration ?? fallbackDuration,
      seek,
      toggle,
    }),
    [clock, src, playing, mediaDuration, fallbackDuration, seek, toggle],
  );

  return (
    <PlayerContext.Provider value={value}>
      {src && (
        <audio
          ref={audioRef}
          src={src}
          preload="auto"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
          onLoadedMetadata={(e) => setMediaDuration(e.currentTarget.duration)}
          onSeeked={(e) => clock.setTime(e.currentTarget.currentTime)}
          onTimeUpdate={(e) => {
            if (e.currentTarget.paused) clock.setTime(e.currentTarget.currentTime);
          }}
        />
      )}
      {children}
    </PlayerContext.Provider>
  );
}

export function usePlayer(): PlayerContextValue {
  const context = useContext(PlayerContext);
  if (!context) throw new Error("usePlayer must be used inside PlayerProvider");
  return context;
}
