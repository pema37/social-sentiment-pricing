export type LaunchAgent = "scanner" | "validator" | "assessor";

export type ThoughtType =
  | "observation"
  | "analysis"
  | "hypothesis"
  | "decision"
  | "recommendation";

export type ThreatLevel = "none" | "low" | "medium" | "high" | "critical";

export interface StreamEvent {
  agent?: LaunchAgent;
  thought_type?: ThoughtType;
  content?: string;
  is_final?: boolean;
  metadata?: Record<string, unknown>;
  done?: boolean;
  error?: string;
}

export interface Assessment {
  threat_level: ThreatLevel;
  actions: string[];
  urgency: "immediate" | "soon" | "monitor";
}


