import { useSyncExternalStore } from "react";
import { findSegmentIndex } from "./chords";

/**
 * Playback time as an external store. Components subscribe to exactly what they need:
 * the playhead re-renders every frame, chord lists only when the active index changes.
 */
export class PlaybackClock {
  private time = 0;
  private readonly listeners = new Set<() => void>();

  getTime = (): number => this.time;

  setTime(time: number): void {
    if (time === this.time) return;
    this.time = time;
    for (const listener of this.listeners) listener();
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
}

export function usePlaybackTime(clock: PlaybackClock): number {
  return useSyncExternalStore(clock.subscribe, clock.getTime, () => 0);
}

export function useActiveIndex(clock: PlaybackClock, starts: readonly number[]): number {
  return useSyncExternalStore(
    clock.subscribe,
    () => findSegmentIndex(starts, clock.getTime()),
    () => -1,
  );
}
