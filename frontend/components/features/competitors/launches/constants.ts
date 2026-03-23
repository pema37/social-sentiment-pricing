export interface LaunchAgentConfig {
  readonly name: string;
  readonly description: string;
  readonly textColor: string;
  readonly borderActive: string;
  readonly bgActive: string;
  readonly labelColor: string;
}

export const LAUNCH_AGENTS: Record<string, LaunchAgentConfig> = {
  scanner: {
    name: "Scanner Agent",
    description: "Detects launch signals from images/text",
    textColor: "text-blue-400",
    borderActive: "border-blue-500",
    bgActive: "bg-blue-500/10",
    labelColor: "text-blue-400",
  },
  validator: {
    name: "Validator Agent",
    description: "Confirms launch details and timing",
    textColor: "text-purple-400",
    borderActive: "border-purple-500",
    bgActive: "bg-purple-500/10",
    labelColor: "text-purple-400",
  },
  assessor: {
    name: "Assessor Agent",
    description: "Evaluates threat and recommends response",
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

export const THREAT_STYLES: Record<string, { text: string; border: string; bg: string }> = {
  none: { text: "text-muted-foreground", border: "border-border", bg: "bg-muted/30" },
  low: { text: "text-green-600", border: "border-green-500", bg: "bg-green-500/10" },
  medium: { text: "text-yellow-600", border: "border-yellow-500", bg: "bg-yellow-500/10" },
  high: { text: "text-orange-600", border: "border-orange-500", bg: "bg-orange-500/10" },
  critical: { text: "text-red-600", border: "border-red-500", bg: "bg-red-500/10" },
};


