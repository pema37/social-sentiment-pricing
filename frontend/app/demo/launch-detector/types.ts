export type LaunchAgent = "scanner" | "validator" | "assessor";
export type ThoughtType = "observation" | "analysis" | "hypothesis" | "decision" | "recommendation";
export type ThreatLevel = "none" | "low" | "medium" | "high" | "critical";

export interface LaunchMessage {
  agent: LaunchAgent;
  thought_type: ThoughtType | null;
  content: string;
  is_final: boolean;
  metadata?: Record<string, unknown>;
}

export interface StreamEvent {
  agent?: LaunchAgent;
  thought_type?: ThoughtType;
  content?: string;
  is_final?: boolean;
  metadata?: Record<string, unknown>;
  done?: boolean;
  error?: string;
}

export interface ScanResult {
  launch_detected: boolean;
  analysis: string;
}

export interface ValidatedLaunch {
  product_name: string;
  is_new_launch: boolean;
  confidence: number;
  launch_date?: string;
}

export interface Assessment {
  threat_level: ThreatLevel;
  actions: string[];
  urgency: "immediate" | "soon" | "monitor";
}


