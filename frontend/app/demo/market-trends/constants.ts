import type { TrendAgent, SimulateTrend, ThoughtType } from "./types";

export const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

export interface TrendAgentConfig {
  readonly name: string;
  readonly description: string;
  readonly textColor: string;
  readonly borderActive: string;
  readonly bgActive: string;
  readonly labelColor: string;
}

export const TREND_AGENTS: Record<TrendAgent, TrendAgentConfig> = {
  observer: {
    name: "Market Observer",
    description: "Scans data and identifies patterns",
    textColor: "text-cyan-400",
    borderActive: "border-cyan-500",
    bgActive: "bg-cyan-500/10",
    labelColor: "text-cyan-400",
  },
  analyst: {
    name: "Trend Analyst",
    description: "Interprets drivers and correlations",
    textColor: "text-violet-400",
    borderActive: "border-violet-500",
    bgActive: "bg-violet-500/10",
    labelColor: "text-violet-400",
  },
  forecaster: {
    name: "Market Forecaster",
    description: "Predicts movement and recommends action",
    textColor: "text-amber-400",
    borderActive: "border-amber-500",
    bgActive: "bg-amber-500/10",
    labelColor: "text-amber-400",
  },
};

export interface ThoughtLabelConfig {
  readonly label: string;
  readonly color: string;
}

export const THOUGHT_LABELS: Record<ThoughtType, ThoughtLabelConfig> = {
  observation: { label: "Observation", color: "text-cyan-400" },
  analysis: { label: "Analysis", color: "text-violet-400" },
  hypothesis: { label: "Hypothesis", color: "text-blue-400" },
  decision: { label: "Decision", color: "text-amber-400" },
  recommendation: { label: "Recommendation", color: "text-green-400" },
};

export const DIRECTION_STYLES: Record<string, { text: string; border: string; bg: string }> = {
  strong_up: { text: "text-green-400", border: "border-green-500", bg: "bg-green-500/10" },
  up: { text: "text-emerald-400", border: "border-emerald-500", bg: "bg-emerald-500/10" },
  stable: { text: "text-gray-400", border: "border-gray-500", bg: "bg-gray-500/10" },
  down: { text: "text-orange-400", border: "border-orange-500", bg: "bg-orange-500/10" },
  strong_down: { text: "text-red-400", border: "border-red-500", bg: "bg-red-500/10" },
};

export const SIMULATE_OPTIONS: { value: SimulateTrend; label: string }[] = [
  { value: "bullish", label: "Bullish (Uptrend)" },
  { value: "neutral", label: "Neutral (Stable)" },
  { value: "bearish", label: "Bearish (Downtrend)" },
];

export const CATEGORY_OPTIONS = [
  "electronics",
  "fashion",
  "home",
  "beauty",
  "sports",
  "toys",
  "automotive",
  "grocery",
];


