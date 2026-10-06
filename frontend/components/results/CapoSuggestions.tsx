import { Guitar } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AnalysisResult } from "@/types/analysis";

export function CapoSuggestions({
  result,
  className,
}: {
  result: AnalysisResult;
  className?: string;
}) {
  const { capo_suggestions: options, capo_note: note } = result;
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Guitar className="h-4 w-4 text-violet-600" /> Capo suggestions
        </CardTitle>
        <p className="text-sm text-zinc-500">{note}</p>
      </CardHeader>
      {options.length > 0 && (
        <CardContent>
          <ul className="grid gap-3 sm:grid-cols-3">
            {options.map((option, i) => (
              <li
                key={option.capo}
                className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800"
              >
                <div className="flex items-baseline justify-between">
                  <span className="text-lg font-bold">Capo {option.capo}</span>
                  {i === 0 && <span className="text-xs font-medium text-violet-600">Easiest</span>}
                </div>
                <div className="text-sm text-zinc-500">Play in {option.play_key}</div>
                <div className="mt-2 font-mono text-sm">{option.play_chords.join("  ")}</div>
                <div className="mt-1 text-xs text-zinc-500">
                  {Math.round(option.playability * 100)}% open chords
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      )}
    </Card>
  );
}
