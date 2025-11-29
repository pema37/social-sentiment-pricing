// Sentiment can only be one of these three values
export type SentimentType = 'positive' | 'negative' | 'neutral';

// Sentiment type - represents a single sentiment analysis result
export interface Sentiment {
  id: string;                   // Unique identifier
  product_id: string;           // Which product this sentiment is for
  score: number;                // Sentiment score (-1 to 1, or 0 to 100)
  sentiment_type: SentimentType; // positive, negative, or neutral
  source: string;               // Where it came from (e.g., "twitter", "reddit")
  content: string;              // The actual text that was analyzed
  analyzed_at: string;          // When the analysis was performed
  created_at: string;           // When this record was created
}

// Aggregated sentiment data for a product
export interface SentimentSummary {
  product_id: string;           // Which product
  average_score: number;        // Average sentiment score
  total_mentions: number;       // Total number of mentions analyzed
  positive_count: number;       // How many positive mentions
  negative_count: number;       // How many negative mentions
  neutral_count: number;        // How many neutral mentions
  trend: 'up' | 'down' | 'stable'; // Is sentiment improving or declining?
}

// What you send to analyze new content
export interface SentimentAnalysisRequest {
  product_id: string;           // Which product to associate with
  content: string;              // The text to analyze
  source: string;               // Where this text came from
}
