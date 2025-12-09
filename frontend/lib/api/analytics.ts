// types/analytics.ts

export interface DashboardStats {
  products_tracked: number;
  products_change: number;
  avg_sentiment: number;
  sentiment_change: number;
  pending_suggestions: number;
  urgent_suggestions: number;
  competitors_count: number;
  competitors_new: number;
}

export interface SentimentTrendPoint {
  date: string;
  score: number;
  mentions: number;
}

export interface RevenueTrendPoint {
  month: string;
  revenue: number;
  baseline: number;
}

export interface Alert {
  id: string;
  type: 'critical' | 'warning' | 'success' | 'info';
  title: string;
  description: string;
  created_at: string;
  is_read: boolean;
}

export interface ActivityItem {
  id: string;
  action: string;
  target: string;
  created_at: string;
  type: 'price' | 'sentiment' | 'competitor' | 'rule';
}
