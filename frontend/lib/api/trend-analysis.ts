/**
 * Trend Analysis API Client
 * API functions for the AI trend analysis feature.
 */

import { api } from './client';
import type {
  TrendAnalysisRequest,
  TrendAnalysisResponse,
  PricingOpportunity,
  RiskDetectionResponse,
  AIInsight,
  QuickStatsResponse,
} from '@/types/trend-analysis';

const BASE_URL = '/api/v1/trend-analysis';

/**
 * Run comprehensive AI trend analysis.
 */
export async function runTrendAnalysis(
  request: TrendAnalysisRequest = {}
): Promise<TrendAnalysisResponse> {
  return api.post<TrendAnalysisResponse>(`${BASE_URL}/analyze`, {
    days: request.days ?? 30,
    product_ids: request.product_ids ?? null,
    use_model: request.use_model ?? 'gemini',
  });
}

/**
 * Analyze a specific product for pricing opportunities.
 */
export async function analyzeProductOpportunity(
  productId: string,
  useModel: 'openai' | 'gemini' = 'gemini'
): Promise<PricingOpportunity> {
  return api.post<PricingOpportunity>(
    `${BASE_URL}/opportunity/${productId}?use_model=${useModel}`
  );
}

/**
 * Detect risks across all products.
 */
export async function detectRisks(
  useModel: 'openai' | 'gemini' = 'gemini'
): Promise<RiskDetectionResponse> {
  return api.post<RiskDetectionResponse>(`${BASE_URL}/risks`, {
    use_model: useModel,
  });
}

/**
 * Generate a market insight report.
 */
export async function generateInsight(
  days: number = 30,
  useModel: 'openai' | 'gemini' = 'gemini'
): Promise<AIInsight> {
  return api.post<AIInsight>(`${BASE_URL}/insight`, {
    days,
    use_model: useModel,
  });
}

/**
 * Get quick stats for the dashboard.
 */
export async function getQuickStats(): Promise<QuickStatsResponse> {
  return api.get<QuickStatsResponse>(`${BASE_URL}/quick-stats`);
}

// Query keys re-exported from centralized registry
// See: lib/api/query-keys.ts



