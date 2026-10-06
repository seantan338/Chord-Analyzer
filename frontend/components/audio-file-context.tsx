"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

/**
 * Keeps the user's selected audio File in memory so the results page can play it.
 * The server never stores audio permanently; after a full page reload the user can
 * re-attach the file for playback.
 */
interface AudioFileContextValue {
  getFile: (jobId: string) => File | null;
  setFile: (jobId: string, file: File) => void;
}

const AudioFileContext = createContext<AudioFileContextValue | null>(null);

export function AudioFileProvider({ children }: { children: ReactNode }) {
  const [entry, setEntry] = useState<{ jobId: string; file: File } | null>(null);

  const getFile = useCallback(
    (jobId: string) => (entry && entry.jobId === jobId ? entry.file : null),
    [entry],
  );
  const setFile = useCallback((jobId: string, file: File) => setEntry({ jobId, file }), []);
  const value = useMemo(() => ({ getFile, setFile }), [getFile, setFile]);

  return <AudioFileContext.Provider value={value}>{children}</AudioFileContext.Provider>;
}

export function useAudioFiles(): AudioFileContextValue {
  const context = useContext(AudioFileContext);
  if (!context) throw new Error("useAudioFiles must be used inside AudioFileProvider");
  return context;
}
