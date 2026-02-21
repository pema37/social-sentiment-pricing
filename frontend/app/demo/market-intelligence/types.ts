/**
 * Market Intelligence Demo - Shared Types
 *
 * DeveloperWeek 2026 Hackathon - You.com Challenge Track
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
  price_range_low: number;
  price_range_high: number;
  risk_level: string;
  strategy: string;
  reasoning: string;
  key_factors: string[];
  price_change_percent: number;
  sources_used: number;
}

export interface SourceLink {
  title: string;
  url: string;
}

export type AnalysisStatus = "idle" | "analyzing" | "complete" | "error";

export type AgentKey = "scout" | "analyst" | "strategist";


