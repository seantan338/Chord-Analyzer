"use client";

import { AudioLines, FileText, LayoutDashboard, Music2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useAudioFiles } from "@/components/audio-file-context";
import { AudioPlayerBar } from "@/components/player/AudioPlayerBar";
import { PlayerProvider } from "@/components/player/player-context";
import { Segmented } from "@/components/ui/segmented";
import { TabList, TabPanel, type TabItem } from "@/components/ui/tabs";
import { timelineSegments } from "@/lib/chords";
import type { AnalysisResult, ChordMode } from "@/types/analysis";
import { ChordTimeline } from "./ChordTimeline";
import { OverviewPanel } from "./OverviewPanel";
import { SongHeader } from "./SongHeader";

type TabId = "overview" | "timeline" | "sheet" | "transpose";

const TABS: TabItem<TabId>[] = [
  { id: "overview", label: "Overview", icon: <LayoutDashboard className="h-4 w-4" /> },
  { id: "timeline", label: "Chord Timeline", icon: <AudioLines className="h-4 w-4" /> },
  { id: "sheet", label: "Chord Sheet", icon: <FileText className="h-4 w-4" /> },
  { id: "transpose", label: "Transpose", icon: <Music2 className="h-4 w-4" /> },
];

export function ResultsView({ jobId, result }: { jobId: string; result: AnalysisResult }) {
  const { getFile, setFile } = useAudioFiles();
  const [mode, setMode] = useState<ChordMode>("original");
  const [tab, setTab] = useState<TabId>("timeline");
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
        </div>

        <div>
          <TabList idPrefix="results" items={TABS} active={tab} onChange={setTab} />
          <TabPanel idPrefix="results" id="overview" active={tab === "overview"}>
            <OverviewPanel result={result} segments={segments} />
          </TabPanel>
          <TabPanel idPrefix="results" id="timeline" active={tab === "timeline"}>
            <ChordTimeline segments={segments} duration={result.metadata.duration} waveform={result.waveform} />
          </TabPanel>
          <TabPanel idPrefix="results" id="sheet" active={tab === "sheet"}>
            <p className="text-sm text-zinc-500">Chord sheet coming in the next phase.</p>
          </TabPanel>
          <TabPanel idPrefix="results" id="transpose" active={tab === "transpose"}>
            <p className="text-sm text-zinc-500">Transposition coming in the next phase.</p>
          </TabPanel>
        </div>
      </div>
      <AudioPlayerBar segments={segments} onAttach={(file) => setFile(jobId, file)} />
    </PlayerProvider>
  );
}
