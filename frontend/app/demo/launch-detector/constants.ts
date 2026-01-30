export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const LAUNCH_AGENTS = {
  scanner: {
    name: "Scanner Agent",
    color: "blue",
    description: "Detects launch signals from images/text"
  },
  validator: {
    name: "Validator Agent",
    color: "purple",
    description: "Confirms launch details and timing"
  },
  assessor: {
    name: "Assessor Agent",
    color: "emerald",
    description: "Evaluates threat and recommends response"
  }
} as const;

export const THOUGHT_LABELS: Record<string, { label: string; color: string }> = {
  observation: { label: "Observing", color: "slate" },
  analysis: { label: "Analyzing", color: "blue" },
  hypothesis: { label: "Theorizing", color: "purple" },
  decision: { label: "Deciding", color: "amber" },
  recommendation: { label: "Recommending", color: "emerald" }
};

export const THREAT_COLORS: Record<string, string> = {
  none: "gray",
  low: "green",
  medium: "yellow",
  high: "orange",
  critical: "red"
};



