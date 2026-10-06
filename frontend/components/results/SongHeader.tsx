import type { ReactNode } from "react";
import { ConfidenceBadge } from "@/components/ui/badge";
import { formatBpm, formatBytes, formatTime, songTitle } from "@/lib/format";
import type { AnalysisResult, ConfidenceLevel } from "@/types/analysis";

function Stat({
  label,
  value,
  level,
  hint,
}: {
  label: string;
  value: ReactNode;
  level?: ConfidenceLevel;
  hint?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 text-2xl font-bold tracking-tight">{value}</div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
        {level && <ConfidenceBadge level={level} short />}
        {hint}
      </div>
    </div>
  );
}

export function SongHeader({ result }: { result: AnalysisResult }) {
  const { metadata, music, view } = result;
  const transposed = view.semitones !== 0;
  const altKey = music.key_alternatives[0]?.key;

  return (
    <header className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          {songTitle(metadata.filename)}
        </h1>
        <p className="mt-1 text-sm text-zinc-500">
          {metadata.filename} · {formatBytes(metadata.file_size)} · {formatTime(metadata.duration)}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          label={transposed ? "Key (transposed)" : "Key"}
          value={music.key}
          level={music.key_confidence_level}
          hint={
            transposed ? (
              <span>Original: {view.original_key}</span>
            ) : music.key_confidence_level !== "high" && altKey ? (
              <span>Could also be {altKey}</span>
            ) : null
          }
        />
        <Stat
          label="Tempo"
          value={formatBpm(music.bpm)}
          level={music.bpm_confidence_level}
          hint={
            music.bpm_alternatives.length > 0 ? (
              <span>
                or {music.bpm_alternatives.map((b) => Math.round(b)).join(" / ")} (half/double feel)
              </span>
            ) : null
          }
        />
        <Stat
          label="Time signature"
          value={music.time_signature}
          level={music.time_signature_confidence_level}
          hint={music.time_signature_confidence_level === "low" ? <span>assumed</span> : null}
        />
        <Stat label="Duration" value={formatTime(metadata.duration)} />
      </div>
    </header>
  );
}
