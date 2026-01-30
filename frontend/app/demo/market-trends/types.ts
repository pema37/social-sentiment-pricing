/**
 * Market Trends Demo - Shared Types
 * 
 * IMPORTANT: ThoughtType must match backend enum exactly
 */

export type TrendAgent = "observer" | "analyst" | "forecaster";


export type ThoughtType = 
  | "observation"
  | "analysis"
  | "hypothesis"
  | "decision"
  | "recommendation";

export type TrendDirection = "strong_up" | "up" | "stable" | "down" | "strong_down";

export type SimulateTrend = "bullish" | "bearish" | "neutral";

export interface Forecast {
  direction: string;
  confidence: number;
  recommended_action: string;
  timeframe: string;
}

export interface MarketData {
  product: string;
  category: string;
  sentiment_score: number;
  sentiment_trend: string;
  volume_24h: number;
  volume_trend: string;
  price_change_7d: number;
  social_mentions: number;
  competitor_activity: string;
  market_position: string;
}

export interface TrendMessage {
  agent: TrendAgent;
  thought_type: ThoughtType | null;
  content: string;
  is_final: boolean;
  metadata?: {
    forecast?: Forecast;
    market_data?: MarketData;
  };
}

export interface StreamEvent {
  agent?: TrendAgent;
  thought_type?: ThoughtType;  
  content?: string;
  is_final?: boolean;
  metadata?: {
    forecast?: Forecast;
    market_data?: MarketData;
  };
  done?: boolean;
  error?: string;
}


