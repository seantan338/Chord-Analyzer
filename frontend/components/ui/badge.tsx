import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";
import { CONFIDENCE_LABEL, CONFIDENCE_SHORT } from "@/lib/confidence";
import type { ConfidenceLevel } from "@/types/analysis";

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        className,
      )}
      {...props}
    />
  );
}

const LEVEL_STYLES: Record<ConfidenceLevel, string> = {
  high: "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300",
  medium:
    "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300",
  low: "border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300",
};

export function ConfidenceBadge({ level, short = false }: { level: ConfidenceLevel; short?: boolean }) {
  return (
    <Badge className={LEVEL_STYLES[level]} title={CONFIDENCE_LABEL[level]}>
      <span
        aria-hidden
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          level === "high" ? "bg-emerald-500" : level === "medium" ? "bg-amber-500" : "bg-rose-500",
        )}
      />
      {short ? CONFIDENCE_SHORT[level] : CONFIDENCE_LABEL[level]}
    </Badge>
  );
}
