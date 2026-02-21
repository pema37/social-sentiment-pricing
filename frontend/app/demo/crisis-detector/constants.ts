export const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

export interface CrisisAgentConfig {
  readonly name: string;
  readonly description: string;
  readonly textColor: string;
  readonly borderActive: string;
  readonly bgActive: string;
  readonly labelColor: string;
}

export const CRISIS_AGENTS: Record<string, CrisisAgentConfig> = {
  monitor: {
    name: "Monitor Agent",
    description: "Scans sentiment for anomalies",
    textColor: "text-blue-400",
    borderActive: "border-blue-500",
    bgActive: "bg-blue-500/10",
    labelColor: "text-blue-400",
  },
  investigator: {
    name: "Investigator Agent",
    description: "Identifies crisis root cause",
    textColor: "text-purple-400",
    borderActive: "border-purple-500",
    bgActive: "bg-purple-500/10",
    labelColor: "text-purple-400",
  },
  response: {
    name: "Response Agent",
    description: "Recommends crisis actions",
    textColor: "text-emerald-400",
    borderActive: "border-emerald-500",
    bgActive: "bg-emerald-500/10",
    labelColor: "text-emerald-400",
  },
} as const;

export interface ThoughtLabelConfig {
  readonly label: string;
  readonly color: string;
}

export const THOUGHT_LABELS: Record<string, ThoughtLabelConfig> = {
  observation: { label: "Observing", color: "text-slate-400" },
  analysis: { label: "Analyzing", color: "text-blue-400" },
  hypothesis: { label: "Theorizing", color: "text-purple-400" },
  decision: { label: "Deciding", color: "text-amber-400" },
  recommendation: { label: "Recommending", color: "text-emerald-400" },
};

export const SEVERITY_STYLES: Record<string, { text: string; border: string; bg: string }> = {
  none: { text: "text-green-400", border: "border-green-500", bg: "bg-green-500/10" },
  low: { text: "text-yellow-400", border: "border-yellow-500", bg: "bg-yellow-500/10" },
  medium: { text: "text-orange-400", border: "border-orange-500", bg: "bg-orange-500/10" },
  high: { text: "text-red-400", border: "border-red-500", bg: "bg-red-500/10" },
  critical: { text: "text-red-400", border: "border-red-500", bg: "bg-red-500/10" },
};

