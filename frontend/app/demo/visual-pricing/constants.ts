export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

export interface AgentConfig {
  name: string;
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
  description: string;
}

export const AGENT_CONFIG: Record<string, AgentConfig> = {
  scout: {
    name: "Scout Agent",
    label: "SCOUT",
    color: "text-blue-500",
    bgColor: "bg-blue-500/10",
    borderColor: "border-blue-500/30",
    description: "Extracting competitor data from screenshot...",
  },
  analyst: {
    name: "Analyst Agent",
    label: "ANALYST",
    color: "text-purple-500",
    bgColor: "bg-purple-500/10",
    borderColor: "border-purple-500/30",
    description: "Comparing prices and analyzing market position...",
  },
  strategist: {
    name: "Strategist Agent",
    label: "STRATEGIST",
    color: "text-emerald-500",
    bgColor: "bg-emerald-500/10",
    borderColor: "border-emerald-500/30",
    description: "Calculating optimal pricing strategy...",
  },
};

export const THOUGHT_LABELS: Record<string, string> = {
  observation: "Observing",
  analysis: "Analyzing",
  hypothesis: "Hypothesis",
  decision: "Deciding",
  recommendation: "Recommending",
};


