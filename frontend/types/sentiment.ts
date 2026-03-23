// Sentiment domain types
// AUTO-SYNCED with backend via openapi-typescript
// Last synced: 2026-01-08
// Source: components["schemas"]["SentimentAnalysisResponse"], etc.

// ============================================
// ENUMS / UNION TYPES
// ============================================

/**
 * Sentiment classification labels
 */
export type SentimentLabel = 
  | 'very_negative' 
  | 'negative' 
  | 'neutral' 
  | 'positive' 
  | 'very_positive';

/**
 * Sentiment trend direction
 */
export type SentimentTrendDirection = 'up' | 'down' | 'stable';

/**
 * Source platforms for social mentions
 */
export type SentimentSource = 
  | 'twitter' 
  | 'reddit' 
  | 'manual' 
  | 'news' 
  | 'instagram' 
  | 'facebook' 
  | 'youtube';

// ============================================
// SOCIAL MENTION TYPES
// ============================================

/**
 * Social mention from the API
 * Matches: components["schemas"]["MentionResponse"]
 */
export interface SocialMention {
  id: string;
  product_id: string;
  source: string;
  source_id: string | null;
  content: string;
  author: string | null;
  author_followers: number | null;
  engagement_count: number | null;
  url: string | null;
  published_at: string | null;
  collected_at: string;
  processed: boolean;
  // Sentiment fields (populated after analysis)
  sentiment_score: number | null;
  sentiment_label: SentimentLabel | null;
}

/**
 * Paginated mentions response
 */
export interface PaginatedMentions {
  items: SocialMention[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ============================================
// SENTIMENT ANALYSIS TYPES
// ============================================

/**
 * Request to analyze sentiment
 * Matches: components["schemas"]["SentimentAnalysisRequest"]
 */
export interface AnalyzeRequest {
  product_id: string;
  content: string;
  source?: SentimentSource;
  author?: string | null;
  url?: string | null;
  use_ai?: boolean;  // Use Gemini 2.0 Flash for analysis
}

/**
 * Response from sentiment analysis
 * Matches: components["schemas"]["SentimentAnalysisResponse"]
 */
export interface AnalyzeResponse {
  id?: string;
  sentiment_id?: string;
  product_id?: string;
  content?: string;
  text?: string;
  source?: string;
  sentiment_score: number;
  sentiment_label: SentimentLabel;
  confidence: number;
  emotions?: {
    positive: number;
    negative: number;
    neutral: number;
  };
  topics?: string[];
  is_sarcastic?: boolean;
  ai_powered?: boolean;
  analyzed_by?: 'vader' | 'gemini' | 'hybrid';
  created_at?: string;
}

// ============================================
// SENTIMENT SUMMARY & TRENDS
// ============================================

/**
 * Sentiment data point for charts
 */
export interface SentimentDataPoint {
  timestamp: string;
  score: number;
  mention_count: number;
}

/**
 * Sentiment trend response
 * Matches: components["schemas"]["SentimentTrendResponse"]
 */
export interface SentimentTrend {
  product_id: string | null;
  period_days: number;
  current_score: number | null;
  previous_score: number | null;
  change: number | null;
  trend: SentimentTrendDirection;
  timeline: SentimentDataPoint[];
}

/**
 * Aggregated sentiment summary
 * Matches: components["schemas"]["SentimentSummaryResponse"]
 */
export interface SentimentSummary {
  product_id: string;
  average_score: number;
  total_mentions: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  trend: SentimentTrendDirection;
}

// ============================================
// AI STATUS
// ============================================

/**
 * AI status response
 * Matches: components["schemas"]["AIStatusResponse"]
 */
export interface AIStatusResponse {
  openai_available: boolean;
  gemini_available?: boolean;
  model: string | null;
  features: string[];
}

// ============================================
// FETCH MENTIONS REQUEST
// ============================================

/**
 * Request to fetch mentions from external sources
 * Matches: components["schemas"]["FetchMentionsRequest"]
 */
export interface FetchMentionsRequest {
  product_id: string;
  sources?: SentimentSource[];
  keywords?: string[];
  limit?: number;
}

/**
 * Response from fetch mentions
 * Matches: components["schemas"]["FetchMentionsResponse"]
 */
export interface FetchMentionsResponse {
  product_id: string;
  mentions_found: number;
  mentions_analyzed: number;
  sources_searched: string[];
  errors: string[];
}
