import type { Metadata } from "next";
import { AnalysisView } from "@/components/results/AnalysisView";

export const metadata: Metadata = { title: "Analysis · Chord Analyzer" };

export default async function AnalysisPage(props: PageProps<"/analysis/[jobId]">) {
  const { jobId } = await props.params;
  return <AnalysisView jobId={jobId} />;
}
