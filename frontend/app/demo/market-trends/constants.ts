import type { TrendAgent, SimulateTrend } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

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

export const THOUGHT_LABELS: Record<string, { label: string; color: string }> = {
  status: { label: "Status", color: "gray" },
  observation: { label: "Observation", color: "cyan" },
  pattern: { label: "Pattern", color: "blue" },
  signal: { label: "Signal", color: "teal" },
  insight: { label: "Insight", color: "violet" },
  driver: { label: "Driver", color: "purple" },
  risk: { label: "Risk", color: "red" },
  opportunity: { label: "Opportunity", color: "green" },
  forecast: { label: "Forecast", color: "amber" },
  outlook: { label: "Outlook", color: "yellow" },
  action: { label: "Action", color: "orange" },
  timing: { label: "Timing", color: "pink" },
  conclusion: { label: "Conclusion", color: "emerald" }
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

