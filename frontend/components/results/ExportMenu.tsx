"use client";

import { Check, Copy, Download } from "lucide-react";
import { useState } from "react";
import { buttonClasses, Button } from "@/components/ui/button";
import { ApiError, exportUrl, fetchExportText, type ExportFormat } from "@/lib/api";
import type { ChordMode } from "@/types/analysis";

const DOWNLOADS: { format: ExportFormat; label: string }[] = [
  { format: "txt", label: "TXT" },
  { format: "markdown", label: "Markdown" },
  { format: "json", label: "JSON" },
];

/** Copy / download the chord sheet exactly as the API exports it (current key + mode). */
export function ExportMenu({
  jobId,
  semitones,
  mode,
}: {
  jobId: string;
  semitones: number;
  mode: ChordMode;
}) {
  const [status, setStatus] = useState<"idle" | "copied" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);

  async function copy() {
    try {
      const text = await fetchExportText(jobId, "txt", { semitones, mode });
      await navigator.clipboard.writeText(text);
      setStatus("copied");
      setMessage(null);
      window.setTimeout(() => setStatus("idle"), 2000);
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof ApiError ? err.message : "Copy failed. Try downloading instead.");
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" size="sm" onClick={() => void copy()}>
          {status === "copied" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          {status === "copied" ? "Copied" : "Copy"}
        </Button>
        {DOWNLOADS.map(({ format, label }) => (
          <a
            key={format}
            href={exportUrl(jobId, format, { semitones, mode })}
            className={buttonClasses("secondary", "sm")}
            download
          >
            <Download className="h-4 w-4" /> {label}
          </a>
        ))}
      </div>
      {message && <p className="text-xs text-rose-600">{message}</p>}
    </div>
  );
}
