/**
 * Market Intelligence Demo - Constants
 *
 * DeveloperWeek 2026 Hackathon - You.com Challenge Track
 */

export const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

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
    color: "text-blue-400",
    bgColor: "bg-blue-500/10",
    borderColor: "border-blue-500/30",
    description: "Searching live web for competitor prices & market data...",
  },
  analyst: {
    name: "Analyst Agent",
    label: "ANALYST",
    color: "text-amber-400",
    bgColor: "bg-amber-500/10",
    borderColor: "border-amber-500/30",
    description: "Synthesizing market position & sentiment analysis...",
  },
  strategist: {
    name: "Strategist Agent",
    label: "STRATEGIST",
    color: "text-emerald-400",
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

export const CURRENCY_OPTIONS = [
  { value: "USD", label: "USD ($)" },
  { value: "EUR", label: "EUR (€)" },
  { value: "GBP", label: "GBP (£)" },
  { value: "CAD", label: "CAD ($)" },
] as const;


