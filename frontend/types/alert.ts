// Alert domain types
// AUTO-SYNCED with backend via openapi-typescript
// Last synced: 2026-01-08
// Source: components["schemas"]["AlertConfigurationCreate"], AlertRead, etc.

// ============================================
// ENUMS / UNION TYPES
// ============================================

/**
 * Alert severity levels
 * Matches: components["schemas"]["AlertSeverity"]
 */
export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';

/**
 * Alert lifecycle status
 * Matches: components["schemas"]["AlertStatus"]
 */
export type AlertStatus = 'pending' | 'sent' | 'failed' | 'acknowledged' | 'resolved';

/**
 * Types of alerts the system can generate
 * Matches: components["schemas"]["AlertType"]
 */
export type AlertType =
  | 'sentiment_drop'
  | 'sentiment_spike'
  | 'volume_surge'
  | 'viral_mention'
  | 'competitor_price_change'
  | 'price_recommendation'
  | 'price_applied'
  | 'trend_detected'
  | 'anomaly_detected';

/**
 * Notification delivery channels
 * Matches: components["schemas"]["AlertChannel"]
 */
export type AlertChannel = 'email' | 'slack' | 'webhook' | 'in_app';

// ============================================
// ALERT TYPES
// ============================================

/**
 * Alert response from GET endpoints
 * Matches: components["schemas"]["AlertRead"]
 */
export interface Alert {
  id: string;
  user_id: string;
  configuration_id: string | null;
  alert_type: AlertType;
  severity: AlertSeverity;
  title: string;
  message: string;
  product_id: string | null;
  competitor_id: string | null;
  recommendation_id: string | null;
  data: Record<string, unknown>;
  status: AlertStatus;
  channels_sent: string[];
  channels_failed: string[];
  created_at: string;
  sent_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  resolved_at: string | null;
}

/**
 * Alert stats for dashboard
 * Matches: components["schemas"]["AlertStats"]
 */
export interface AlertStats {
  total_unread: number;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
  recent_24h: number;
}

/**
 * Paginated alerts response
 */
export interface PaginatedAlerts {
  items: Alert[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/**
 * Alert filter params for list endpoint
 */
export interface AlertFilterParams {
  skip?: number;
  limit?: number;
  status?: AlertStatus;
  severity?: AlertSeverity;
  alert_type?: AlertType;
  product_id?: string;
}

// ============================================
// ALERT CONFIGURATION TYPES
// ============================================

/**
 * Alert configuration response
 * Matches: components["schemas"]["AlertConfigurationRead"]
 */
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
  channel_settings: Record<string, unknown>;
  cooldown_minutes: number;
  max_per_day: number;
  created_at: string;
  updated_at: string;
  last_triggered_at: string | null;
}

/**
 * Create alert configuration request
 * Matches: components["schemas"]["AlertConfigurationCreate"]
 */
export interface AlertConfigurationCreate {
  name: string;
  description?: string | null;
  alert_type: AlertType;
  is_active?: boolean;                    // Default: true
  product_ids?: string[] | null;
  conditions?: Record<string, unknown>;
  channels?: AlertChannel[];              // Default: ["in_app"]
  channel_settings?: Record<string, unknown>;
  cooldown_minutes?: number;              // Default: 60
  max_per_day?: number;                   // Default: 10
}

/**
 * Update alert configuration request
 * Matches: components["schemas"]["AlertConfigurationUpdate"]
 */
export interface AlertConfigurationUpdate {
  name?: string | null;
  description?: string | null;
  is_active?: boolean | null;
  product_ids?: string[] | null;
  conditions?: Record<string, unknown> | null;
  channels?: AlertChannel[] | null;
  channel_settings?: Record<string, unknown> | null;
  cooldown_minutes?: number | null;
  max_per_day?: number | null;
}

// AlertAnalytics is defined in types/analytics.ts and exported from there
