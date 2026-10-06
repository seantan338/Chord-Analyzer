import type { ConfidenceLevel } from "@/types/analysis";

export const CONFIDENCE_LABEL: Record<ConfidenceLevel, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

export const CONFIDENCE_SHORT: Record<ConfidenceLevel, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};
