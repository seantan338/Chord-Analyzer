"use client";

import { AudioLines, FileText, LayoutDashboard, Music2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useAudioFiles } from "@/components/audio-file-context";
import { AudioPlayerBar } from "@/components/player/AudioPlayerBar";
import { PlayerProvider } from "@/components/player/player-context";
import { Segmented } from "@/components/ui/segmented";
import { TabList, TabPanel, type TabItem } from "@/components/ui/tabs";
import { timelineSegments } from "@/lib/chords";
import { useResultView } from "@/lib/use-result-view";
import type { AnalysisResult, ChordMode } from "@/types/analysis";
import { CapoSuggestions } from "./CapoSuggestions";
import { ChordSheetPanel } from "./ChordSheetPanel";
import { ChordTimeline } from "./ChordTimeline";
import { OverviewPanel } from "./OverviewPanel";
import { SongHeader } from "./SongHeader";
import { TransposeControls, TransposePanel } from "./TransposePanel";

type TabId = "overview" | "timeline" | "sheet" | "transpose";

const TABS: TabItem<TabId>[] = [
  { id: "overview", label: "Overview", icon: <LayoutDashboard className="h-4 w-4" /> },
  { id: "timeline", label: "Chord Timeline", icon: <AudioLines className="h-4 w-4" /> },
  { id: "sheet", label: "Chord Sheet", icon: <FileText className="h-4 w-4" /> },
  { id: "transpose", label: "Transpose", icon: <Music2 className="h-4 w-4" /> },
];

export function ResultsView({
  jobId,
  result: original,
}: {
  jobId: string;
  result: AnalysisResult;
}) {
  const { getFile, setFile } = useAudioFiles();
  const [mode, setMode] = useState<ChordMode>("original");
  const [tab, setTab] = useState<TabId>("timeline");
  const view = useResultView(jobId, original);
  const result = view.result;
  const segments = useMemo(
    () => timelineSegments(result.chords, result.beginner_chords, mode),
    [result, mode],
  );

  return (
    <PlayerProvider file={getFile(jobId)} fallbackDuration={result.metadata.duration}>
      <div className="space-y-6 pb-32">
        <SongHeader result={result} />

        <div className="flex flex-wrap items-center justify-between gap-3">
          <Segmented<ChordMode>
            label="Chord style"
            value={mode}
            onChange={setMode}
            options={[
              { value: "original", label: "Original chords" },
              { value: "beginner", label: "Beginner chords" },
            ]}
          />
          <div className="flex items-center gap-2 text-sm text-zinc-500">
            Transpose
            <TransposeControls
              semitones={view.semitones}
              loading={view.loading}
              onTranspose={view.transpose}
            />
          </div>
        </div>

        <div>
          <TabList idPrefix="results" items={TABS} active={tab} onChange={setTab} />
          <TabPanel idPrefix="results" id="overview" active={tab === "overview"}>
            <OverviewPanel
              result={result}
              segments={segments}
              extra={<CapoSuggestions result={result} className="lg:col-span-3" />}
            />
          </TabPanel>
          <TabPanel idPrefix="results" id="timeline" active={tab === "timeline"}>
            <ChordTimeline
              segments={segments}
              duration={result.metadata.duration}
              waveform={result.waveform}
            />
          </TabPanel>
          <TabPanel idPrefix="results" id="sheet" active={tab === "sheet"}>
            <ChordSheetPanel result={result} mode={mode} />
          </TabPanel>
          <TabPanel idPrefix="results" id="transpose" active={tab === "transpose"}>
            <TransposePanel
              original={original}
              result={result}
              mode={mode}
              semitones={view.semitones}
              loading={view.loading}
              error={view.error}
              onTranspose={view.transpose}
            />
          </TabPanel>
        </div>
      </div>
      <AudioPlayerBar segments={segments} onAttach={(file) => setFile(jobId, file)} />
    </PlayerProvider>
  );
}
