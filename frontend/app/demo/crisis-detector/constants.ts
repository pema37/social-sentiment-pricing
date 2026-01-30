export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const CRISIS_AGENTS = {
  monitor: {
    name: "Monitor Agent",
    color: "blue",
    description: "Scans sentiment for anomalies"
  },
  investigator: {
    name: "Investigator Agent", 
    color: "purple",
    description: "Identifies crisis root cause"
  },
  response: {
    name: "Response Agent",
    color: "emerald",
    description: "Recommends crisis actions"
  }
} as const;

export const THOUGHT_LABELS: Record<string, { label: string; color: string }> = {
  observation: { label: "Observing", color: "slate" },
  analysis: { label: "Analyzing", color: "blue" },
  hypothesis: { label: "Theorizing", color: "purple" },
  decision: { label: "Deciding", color: "amber" },
  recommendation: { label: "Recommending", color: "emerald" }
};

export const SEVERITY_COLORS: Record<string, string> = {
  none: "green",
  low: "yellow", 
  medium: "orange",
  high: "red",
  critical: "red"
};



