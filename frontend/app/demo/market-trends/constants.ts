import type { TrendAgent, SimulateTrend, ThoughtType } from "./types";

export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

export const TREND_AGENTS: Record<TrendAgent, { name: string; description: string; color: string }> = {
  observer: {
    name: "Market Observer",
    description: "Scans data and identifies patterns",
    color: "cyan"
  },
  analyst: {
    name: "Trend Analyst", 
    description: "Interprets drivers and correlations",
    color: "violet"
  },
  forecaster: {
    name: "Market Forecaster",
    description: "Predicts movement and recommends action",
    color: "amber"
  }
};

export const THOUGHT_LABELS: Record<ThoughtType, { label: string; color: string }> = {
  observation: { label: "Observation", color: "cyan" },
  analysis: { label: "Analysis", color: "violet" },
  hypothesis: { label: "Hypothesis", color: "blue" },
  decision: { label: "Decision", color: "amber" },
  recommendation: { label: "Recommendation", color: "green" }
};

export const DIRECTION_COLORS: Record<string, string> = {
  strong_up: "green",
  up: "emerald",
  stable: "gray",
  down: "orange",
  strong_down: "red"
};

export const SIMULATE_OPTIONS: { value: SimulateTrend; label: string }[] = [
  { value: "bullish", label: "Bullish (Uptrend)" },
  { value: "neutral", label: "Neutral (Stable)" },
  { value: "bearish", label: "Bearish (Downtrend)" }
];

export const CATEGORY_OPTIONS = [
  "electronics",
  "fashion",
  "home",
  "beauty",
  "sports",
  "toys",
  "automotive",
  "grocery"
];


