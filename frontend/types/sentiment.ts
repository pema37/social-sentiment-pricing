// Sentiment domain types

export type SentimentLabel = 'very_negative' | 'negative' | 'neutral' | 'positive' | 'very_positive';
export type SentimentTrendDirection = 'up' | 'down' | 'stable';
export type SentimentSource = 'twitter' | 'reddit' | 'manual' | 'news' | 'instagram' | 'facebook' | 'youtube';

// Social mention from the API
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

// Paginated mentions response
export interface PaginatedMentions {
  items: SocialMention[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Request to analyze sentiment
export interface AnalyzeRequest {
  product_id: string;
  content: string;
  source: SentimentSource;
  author?: string;
  url?: string;
}

// Response from sentiment analysis
export interface AnalyzeResponse {
  id: string;
  product_id: string;
  content: string;
  source: string;
  sentiment_score: number;
  sentiment_label: SentimentLabel;
  confidence: number;
  created_at: string;
}

// Sentiment data point for charts
export interface SentimentDataPoint {
  timestamp: string;
  score: number;
  mention_count: number;
}

// Sentiment trend response
export interface SentimentTrend {
  product_id: string | null;
  period_days: number;
  current_score: number | null;
  previous_score: number | null;
  change: number | null;
  trend: SentimentTrendDirection;
  timeline: SentimentDataPoint[];
}

// Aggregated sentiment summary
export interface SentimentSummary {
  product_id: string;
  average_score: number;
  total_mentions: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  trend: SentimentTrendDirection;
}
