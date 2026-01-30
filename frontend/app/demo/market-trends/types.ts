export type TrendAgent = "observer" | "analyst" | "forecaster";

export type ThoughtType = 
  | "status"
  | "observation"
  | "pattern"
  | "signal"
  | "insight"
  | "driver"
  | "risk"
  | "opportunity"
  | "forecast"
  | "outlook"
  | "action"
  | "timing"
  | "conclusion";

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

export interface StreamEvent {
  agent?: TrendAgent;
  thought_type?: ThoughtType;  
  content?: string;
  is_final?: boolean;
  metadata?: {
    forecast?: Forecast;
  };
  done?: boolean;
  error?: string;
  market_data?: MarketData;
}


