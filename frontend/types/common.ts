// types/common.ts
// Shared types used across multiple modules

/** Generic paginated response */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/** Trend direction */
export type TrendDirection = 'up' | 'down' | 'stable';

/** Alert notification channels */
export type AlertChannel = 'email' | 'slack' | 'in_app' | 'webhook';
