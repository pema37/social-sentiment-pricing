// Alert domain types

export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';
export type AlertStatus = 'pending' | 'acknowledged' | 'resolved';

export type AlertType =
  | 'sentiment_drop'
  | 'sentiment_spike'
  | 'price_recommendation'
  | 'competitor_price_change'
  | 'volume_surge'
  | 'viral_mention';

export type AlertChannel = 'email' | 'in_app' | 'slack' | 'webhook';

// Alert from the API
export interface Alert {
  id: string;
  alert_type: string;
  severity: AlertSeverity;
  title: string;
  message: string;
  status: AlertStatus;
  product_id: string | null;
  recommendation_id: string | null;
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

// Alert stats
export interface AlertStats {
  total_unread: number;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
  recent_24h: number;
}

// Paginated alerts
export interface PaginatedAlerts {
  items: Alert[];
  total: number;
  skip: number;
  limit: number;
}

// Alert filter params
export interface AlertFilterParams {
  skip?: number;
  limit?: number;
  status?: AlertStatus;
  severity?: AlertSeverity;
  alert_type?: string;
  product_id?: string;
}

// Alert configuration
export interface AlertConfiguration {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  alert_type: AlertType;
  is_active: boolean;
  product_ids: string[] | null;
  conditions: Record<string, unknown>;
  channels: AlertChannel[];
  channel_settings: Record<string, unknown> | null;
  cooldown_minutes: number;
  max_per_day: number | null;
  created_at: string;
  updated_at: string;
}

// Create alert configuration
export interface AlertConfigurationCreate {
  name: string;
  description?: string;
  alert_type: AlertType;
  is_active?: boolean;
  product_ids?: string[];
  conditions?: Record<string, unknown>;
  channels: AlertChannel[];
  channel_settings?: Record<string, unknown>;
  cooldown_minutes?: number;
  max_per_day?: number;
}

// Update alert configuration
export interface AlertConfigurationUpdate {
  name?: string;
  description?: string;
  alert_type?: AlertType;
  is_active?: boolean;
  product_ids?: string[];
  conditions?: Record<string, unknown>;
  channels?: AlertChannel[];
  channel_settings?: Record<string, unknown>;
  cooldown_minutes?: number;
  max_per_day?: number;
}
