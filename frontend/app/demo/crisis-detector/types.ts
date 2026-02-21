export type CrisisAgent = "monitor" | "investigator" | "response";
export type ThoughtType = "observation" | "analysis" | "hypothesis" | "decision" | "recommendation";
export type Severity = "none" | "low" | "medium" | "high" | "critical";

export interface CrisisMessage {
  agent: CrisisAgent;
  thought_type: ThoughtType | null;
  content: string;
  is_final: boolean;
  metadata?: Record<string, unknown>;
}

export interface StreamEvent {
  agent?: CrisisAgent;
  thought_type?: ThoughtType;
  content?: string;
  is_final?: boolean;
  metadata?: Record<string, unknown>;
  done?: boolean;
  error?: string;
}

