// frontend/types/trust-scoring.ts

/**
 * Trust Scoring / Bot Detection Types
 */

// ─────────────────────────────────────────────────────────────────────────────
// Enums
// ─────────────────────────────────────────────────────────────────────────────

export type TrustLevel = 
  | 'verified' 
  | 'high' 
  | 'medium' 
  | 'low' 
  | 'untrusted' 
  | 'blocked';

export type RiskFlag =
  | 'new_account'
  | 'low_followers'
  | 'high_post_frequency'
  | 'repetitive_content'
  | 'coordinated_timing'
  | 'suspicious_engagement'
  | 'keyword_stuffing'
  | 'link_spam'
  | 'copy_paste'
  | 'sentiment_extreme'
  | 'bot_pattern'
  | 'fake_engagement';

// ─────────────────────────────────────────────────────────────────────────────
// Author Scoring
// ─────────────────────────────────────────────────────────────────────────────

export interface AuthorScoreRequest {
  author_id: string;
  username: string;
  source: string;
  follower_count?: number | null;
  following_count?: number | null;
  post_count?: number | null;
  account_created_at?: string | null;
  is_verified?: boolean;
}

export interface ComponentScores {
  account_age: number;
  followers: number;
  engagement: number;
  history: number;
  verification_bonus: number;
}

export interface AuthorScoreResponse {
  author_id: string;
  source: string;
  trust_score: number;
  trust_level: TrustLevel;
  risk_flags: RiskFlag[];
  risk_score: number;
  component_scores: ComponentScores;
  confidence: number;
  calculated_at: string;
}

export interface BatchAuthorScoreRequest {
  authors: AuthorScoreRequest[];
}

export interface BatchAuthorScoreResponse {
  scores: AuthorScoreResponse[];
  total: number;
  avg_trust_score: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Content Analysis
// ─────────────────────────────────────────────────────────────────────────────

export interface ContentAnalysisRequest {
  content_id: string;
  text: string;
  author_username?: string | null;
}

export interface SpamIndicators {
  excessive_hashtags: boolean;
  excessive_links: boolean;
  keyword_stuffing: boolean;
  all_caps: boolean;
  spam_phrases: boolean;
}

export interface ContentAnalysisResponse {
  content_id: string;
  word_count: number;
  is_duplicate: boolean;
  duplicate_count: number;
  content_quality_score: number;
  originality_score: number;
  risk_flags: RiskFlag[];
  spam_indicators: SpamIndicators;
  is_spam: boolean;
}

export interface BatchContentAnalysisRequest {
  contents: ContentAnalysisRequest[];
}

export interface BatchContentAnalysisResponse {
  analyses: ContentAnalysisResponse[];
  total: number;
  spam_count: number;
  duplicate_count: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Campaign Detection
// ─────────────────────────────────────────────────────────────────────────────

export interface MentionInput {
  mention_id: string;
  author_id: string;
  content: string;
  published_at: string;
  sentiment_score?: number | null;
  source?: string;
}

export interface CampaignSignal {
  signal_type: string;
  strength: number;
  description: string;
}

export interface CampaignDetectionRequest {
  mentions: MentionInput[];
  product_id?: string | null;
  time_window_hours?: number;
}

export interface CampaignDetectionResponse {
  product_id: string | null;
  time_window_hours: number;
  is_campaign_detected: boolean;
  campaign_confidence: number;
  signals: CampaignSignal[];
  metrics: {
    posts_analyzed: number;
    unique_authors: number;
    timing_anomaly_score?: number;
    content_similarity_score?: number;
  };
  suspicious_author_count: number;
  suspicious_content_count: number;
  analyzed_at: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Weighted Sentiment
// ─────────────────────────────────────────────────────────────────────────────

export interface WeightedSentimentRequest {
  mentions: MentionInput[];
  product_id?: string | null;
  period_hours?: number;
  check_campaign?: boolean;
  author_metadata?: Record<string, {
    username?: string;
    follower_count?: number;
    account_created_at?: string;
    is_verified?: boolean;
  }>;
}

export interface RawSentimentStats {
  sentiment: number;
  mention_count: number;
}

export interface AdjustedSentimentStats {
  sentiment: number;
  effective_mentions: number;
}

export interface QualityMetrics {
  high_trust_ratio: number;
  filtered_count: number;
  confidence: number;
}

export interface TrustBreakdown {
  verified: number;
  high: number;
  medium: number;
  low: number;
  untrusted: number;
  blocked: number;
}

export interface WeightedSentimentResponse {
  product_id: string;
  period_hours: number;
  raw: RawSentimentStats;
  adjusted: AdjustedSentimentStats;
  quality: QualityMetrics;
  trust_breakdown: TrustBreakdown;
  campaign_detected: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// Quick Checks
// ─────────────────────────────────────────────────────────────────────────────

export interface QuickSpamCheckRequest {
  text: string;
  username?: string | null;
}

export interface QuickSpamCheckResponse {
  is_spam: boolean;
  spam_score: number;
  reasons: string[];
}

export interface QuickTrustCheckRequest {
  author_id: string;
  username: string;
  source: string;
  follower_count?: number | null;
  account_age_days?: number | null;
}

export interface QuickTrustCheckResponse {
  is_trustworthy: boolean;
  trust_score: number;
  trust_level: TrustLevel;
  risk_flags: string[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Statistics
// ─────────────────────────────────────────────────────────────────────────────

export interface TrustScoringStats {
  content_analyzer: {
    hash_cache_size: number;
    fuzzy_cache_size: number;
    recent_content_size: number;
  };
  config: {
    min_trust_threshold: number;
    new_account_threshold_days: number;
    established_account_threshold_days: number;
  };
  cache_stats: {
    hash_cache_size: number;
    fuzzy_cache_size: number;
    recent_content_size: number;
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// UI Helper Types
// ─────────────────────────────────────────────────────────────────────────────

export interface TrustLevelInfo {
  level: TrustLevel;
  label: string;
  color: string;
  bgColor: string;
  description: string;
}

export interface RiskFlagInfo {
  flag: RiskFlag;
  label: string;
  severity: 'low' | 'medium' | 'high';
  description: string;
}



