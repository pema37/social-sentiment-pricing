/**
 * Trend Analysis Types
 * TypeScript types for the AI trend analysis feature.
 */

// ============================================
// ENUMS
// ============================================

export type TrendDirection = 'rising' | 'falling' | 'stable' | 'volatile';

export type TrendCategory =
  | 'viral_positive'
  | 'viral_negative'
  | 'competitor_launch'
  | 'seasonal'
  | 'news_event'
  | 'market_shift'
  | 'organic_growth'
  | 'organic_decline';

export type OpportunityType =
  | 'price_increase'
  | 'price_decrease'
  | 'hold'
  | 'promotional'
  | 'premium_positioning';

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export type ConfidenceLevel = 'low' | 'medium' | 'high' | 'very_high';

// ============================================
// REQUEST TYPES
// ============================================

export interface TrendAnalysisRequest {
  days?: number;
  product_ids?: string[];
  use_model?: 'openai' | 'gemini';
}

export interface ProductOpportunityRequest {
  product_id: string;
  use_model?: 'openai' | 'gemini';
}

export interface RiskDetectionRequest {
  use_model?: 'openai' | 'gemini';
}

export interface InsightGenerationRequest {
  days?: number;
  use_model?: 'openai' | 'gemini';
}

// ============================================
// RESPONSE TYPES
// ============================================

export interface TrendSignal {
  signal_type: string;
  value: number;
  timestamp: string;
  source: string;
  description: string;
}

export interface TrendPrediction {
  direction: TrendDirection;
  category: TrendCategory;
  confidence: ConfidenceLevel;
  confidence_score: number;
  predicted_change: number;
  timeframe_days: number;
  reasoning: string;
  supporting_signals: TrendSignal[];
}

export interface PricingOpportunity {
  opportunity_type: OpportunityType;
  product_id: string;
  product_name: string;
  current_price: string;
  suggested_price: string;
  expected_impact: string;
  confidence: ConfidenceLevel;
  confidence_score: number;
  reasoning: string;
  valid_until: string;
  triggers: string[];
}

export interface RiskAlert {
  risk_level: RiskLevel;
  risk_type: string;
  title: string;
  description: string;
  affected_products: string[];
  recommended_actions: string[];
  detected_at: string;
  expires_at: string | null;
}

export interface AIInsight {
  title: string;
  summary: string;
  detailed_analysis: string;
  key_factors: string[];
  data_points_analyzed: number;
  generated_at: string;
  model_used: string;
}

export interface TrendAnalysisResponse {
  analysis_id: string;
  generated_at: string;
  market_sentiment: TrendDirection;
  market_sentiment_score: number;
  predictions: TrendPrediction[];
  opportunities: PricingOpportunity[];
  risks: RiskAlert[];
  insights: AIInsight[];
  executive_summary: string;
  recommended_actions: string[];
  products_analyzed: number;
  mentions_analyzed: number;
  time_range_days: number;
}

export interface RiskDetectionResponse {
  risks: RiskAlert[];
  overall_risk_level: RiskLevel;
  summary: string;
  generated_at: string;
}

export interface QuickStatsResponse {
  current_sentiment: number;
  sentiment_trend: TrendDirection;
  sentiment_change_7d: number;
  mentions_today: number;
  mentions_7d: number;
  volume_change_percent: number;
  active_opportunities: number;
  potential_revenue_impact: string;
  active_risks: number;
  highest_risk_level: RiskLevel;
  trending_up: string[];
  trending_down: string[];
  last_updated: string;
}

// ============================================
// UI HELPER TYPES
// ============================================

export interface TrendDisplayInfo {
  label: string;
  color: string;
  icon: string;
  bgColor: string;
}

export interface RiskDisplayInfo {
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
}

export interface ConfidenceDisplayInfo {
  label: string;
  color: string;
  width: string;
}

// ============================================
// HELPER FUNCTIONS
// ============================================

export function getTrendDisplayInfo(direction: TrendDirection): TrendDisplayInfo {
  const info: Record<TrendDirection, TrendDisplayInfo> = {
    rising: {
      label: 'Rising',
      color: 'text-green-600',
      icon: '↑',
      bgColor: 'bg-green-100',
    },
    falling: {
      label: 'Falling',
      color: 'text-red-600',
      icon: '↓',
      bgColor: 'bg-red-100',
    },
    stable: {
      label: 'Stable',
      color: 'text-gray-600',
      icon: '→',
      bgColor: 'bg-gray-100',
    },
    volatile: {
      label: 'Volatile',
      color: 'text-orange-600',
      icon: '↕',
      bgColor: 'bg-orange-100',
    },
  };
  return info[direction];
}

export function getRiskDisplayInfo(level: RiskLevel): RiskDisplayInfo {
  const info: Record<RiskLevel, RiskDisplayInfo> = {
    low: {
      label: 'Low',
      color: 'text-green-700',
      bgColor: 'bg-green-100',
      borderColor: 'border-green-300',
    },
    medium: {
      label: 'Medium',
      color: 'text-yellow-700',
      bgColor: 'bg-yellow-100',
      borderColor: 'border-yellow-300',
    },
    high: {
      label: 'High',
      color: 'text-orange-700',
      bgColor: 'bg-orange-100',
      borderColor: 'border-orange-300',
    },
    critical: {
      label: 'Critical',
      color: 'text-red-700',
      bgColor: 'bg-red-100',
      borderColor: 'border-red-300',
    },
  };
  return info[level];
}

export function getConfidenceDisplayInfo(level: ConfidenceLevel): ConfidenceDisplayInfo {
  const info: Record<ConfidenceLevel, ConfidenceDisplayInfo> = {
    low: {
      label: 'Low Confidence',
      color: 'bg-gray-400',
      width: 'w-1/4',
    },
    medium: {
      label: 'Medium Confidence',
      color: 'bg-yellow-500',
      width: 'w-1/2',
    },
    high: {
      label: 'High Confidence',
      color: 'bg-green-500',
      width: 'w-3/4',
    },
    very_high: {
      label: 'Very High Confidence',
      color: 'bg-green-600',
      width: 'w-full',
    },
  };
  return info[level];
}

export function getOpportunityTypeLabel(type: OpportunityType): string {
  const labels: Record<OpportunityType, string> = {
    price_increase: 'Price Increase',
    price_decrease: 'Price Decrease',
    hold: 'Hold Current Price',
    promotional: 'Run Promotion',
    premium_positioning: 'Premium Positioning',
  };
  return labels[type];
}

export function getCategoryLabel(category: TrendCategory): string {
  const labels: Record<TrendCategory, string> = {
    viral_positive: 'Viral (Positive)',
    viral_negative: 'Viral (Negative)',
    competitor_launch: 'Competitor Launch',
    seasonal: 'Seasonal Trend',
    news_event: 'News Event',
    market_shift: 'Market Shift',
    organic_growth: 'Organic Growth',
    organic_decline: 'Organic Decline',
  };
  return labels[category];
}

export function formatSentimentScore(score: number): string {
  if (score > 0) return `+${score.toFixed(1)}`;
  return score.toFixed(1);
}

export function formatPercentChange(change: number): string {
  const sign = change >= 0 ? '+' : '';
  return `${sign}${change.toFixed(1)}%`;
}


