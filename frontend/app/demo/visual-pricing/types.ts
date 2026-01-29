/**
 * Visual Pricing Demo - Shared Types
 */

export interface AgentMessage {
  agent: "scout" | "analyst" | "strategist";
  thought_type: string | null;
  content: string;
  is_final: boolean;
  metadata?: Record<string, unknown>;
}

export interface PricingRecommendation {
  recommended_price: number;
  confidence: number;
  reasoning: string;
  price_change_percent: number;
  strategy: string;
  risk_level: string;
  key_factors: string[];
}

export type AnalysisStatus = "idle" | "uploading" | "analyzing" | "complete" | "error";

export type AgentKey = "scout" | "analyst" | "strategist";


