// frontend/lib/api/intelligence.ts
// API functions for Intelligence Environment endpoints
// Pattern: matches existing api/products.ts, api/pricing.ts, etc.

import { api } from './client';
import type {
  IEHealthStatus,
  IEDashboard,
  ExperimentStatus,
  CalibrationReport,
  DriftAlert,
  CategoryPerformance,
  DriftSeverity,
} from '@/types/intelligence';

const BASE = '/api/v1/intelligence';

export const intelligenceApi = {
  /** Combined dashboard payload — single call for the frontend. */
  dashboard: (topN = 10) =>
    api.get<IEDashboard>(`${BASE}/dashboard`, { top_n: topN }),

  /** Overall health status of the IE pipeline. */
  health: () =>
    api.get<IEHealthStatus>(`${BASE}/health`),

  /** Thompson Sampling experiment statuses. */
  experiments: (categoryId?: string) =>
    api.get<ExperimentStatus[]>(`${BASE}/experiments`, {
      ...(categoryId && { category_id: categoryId }),
    }),

  /** Single experiment by category. */
  experiment: (categoryId: string) =>
    api.get<ExperimentStatus>(`${BASE}/experiments/${categoryId}`),

  /** Calibration accuracy reports. */
  calibration: (categoryId?: string) =>
    api.get<CalibrationReport[]>(`${BASE}/calibration`, {
      ...(categoryId && { category_id: categoryId }),
    }),

  /** Drift detection alerts. */
  driftAlerts: (params?: { severity?: DriftSeverity; active_only?: boolean }) =>
    api.get<DriftAlert[]>(`${BASE}/drift-alerts`, {
      ...params,
    }),

  /** Category performance metrics. */
  categories: (params?: { min_recommendations?: number; sort_by?: string }) =>
    api.get<CategoryPerformance[]>(`${BASE}/categories`, {
      ...params,
    }),

  /** Single category detail. */
  category: (categoryId: string) =>
    api.get<CategoryPerformance>(`${BASE}/categories/${categoryId}`),
};


