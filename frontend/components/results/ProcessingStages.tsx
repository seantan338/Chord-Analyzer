"use client";

import { Check, Circle, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import { formatBytes } from "@/lib/format";
import type { JobState, StageInfo } from "@/types/analysis";

function useElapsedSeconds(since: string): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return Math.max(0, Math.round((now - new Date(since).getTime()) / 1000));
}

function StageIcon({ state }: { state: StageInfo["state"] }) {
  if (state === "done") return <Check className="h-4 w-4 text-emerald-600" />;
  if (state === "active") return <Loader2 className="h-4 w-4 animate-spin text-violet-600" />;
  if (state === "failed") return <X className="h-4 w-4 text-rose-600" />;
  return <Circle className="h-3 w-3 text-zinc-300 dark:text-zinc-700" />;
}

/**
 * Stage-based progress. The backend reports which stage is running, not a percentage,
 * so no fake percentage is shown.
 */
export function ProcessingStages({ job }: { job: JobState }) {
  const elapsed = useElapsedSeconds(job.created_at);
  const stages: Pick<StageInfo, "label" | "state">[] = [
    { label: "Uploading", state: "done" },
    ...job.stages,
    { label: "Complete", state: job.status === "completed" ? "done" : "pending" },
  ];

  return (
    <Card className="mx-auto max-w-xl">
      <CardContent className="space-y-5 pt-6">
        <div>
          <h1 className="text-xl font-semibold">Analyzing your song…</h1>
          <p className="mt-1 text-sm text-zinc-500">
            {job.filename} · {formatBytes(job.file_size)} · {elapsed}s elapsed
          </p>
        </div>
        {job.status === "queued" && (
          <p className="rounded-lg bg-zinc-50 px-3 py-2 text-sm text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
            Waiting for the analyzer to start…
          </p>
        )}
        <ol className="space-y-2.5" aria-label="Processing stages">
          {stages.map((stage) => (
            <li key={stage.label} className="flex items-center gap-3">
              <span className="flex h-5 w-5 items-center justify-center">
                <StageIcon state={stage.state} />
              </span>
              <span
                className={cn(
                  "text-sm",
                  stage.state === "active" && "font-semibold text-zinc-900 dark:text-zinc-50",
                  stage.state === "pending" && "text-zinc-400",
                  stage.state === "done" && "text-zinc-600 dark:text-zinc-400",
                )}
                aria-current={stage.state === "active" ? "step" : undefined}
              >
                {stage.label}
              </span>
            </li>
          ))}
        </ol>
        <p className="text-xs text-zinc-500">A typical 3–5 minute song takes 10–30 seconds.</p>
      </CardContent>
    </Card>
  );
}
