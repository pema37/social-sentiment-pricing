// Alert domain types

export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical';
export type AlertStatus = 'pending' | 'acknowledged' | 'resolved';

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
