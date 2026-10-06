"use client";

import { useCallback, useEffect, useState } from "react";
import type { AnalysisResult } from "@/types/analysis";
import { ApiError, getResult } from "./api";
import { normalizeShift } from "./keys";

/**
 * Transposed views of an analysis, fetched from the API and cached per shift.
 * While a new view loads, the previous one stays on screen.
 */
export function useResultView(jobId: string, original: AnalysisResult) {
  const [views, setViews] = useState<Record<number, AnalysisResult>>({ 0: original });
  const [requested, setRequested] = useState(0);
  const [shown, setShown] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (views[requested]) return;
    const controller = new AbortController();
    getResult(jobId, { semitones: requested }, controller.signal)
      .then((view) => {
        setViews((current) => ({ ...current, [requested]: view }));
        setShown(requested);
        setError(null);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof ApiError ? err.message : "Could not transpose this song.");
        setRequested(shown);
      });
    return () => controller.abort();
  }, [jobId, requested, shown, views]);

  const transpose = useCallback(
    (semitones: number) => {
      const shift = normalizeShift(semitones);
      setRequested(shift);
      if (views[shift]) setShown(shift);
    },
    [views],
  );

  return {
    result: views[shown],
    semitones: requested,
    loading: requested !== shown,
    error,
    transpose,
  };
}
