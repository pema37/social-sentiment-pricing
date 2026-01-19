// Pricing API
// API functions for pricing rules, recommendations, and settings

import { api } from './client';
import type {
  PricingRule,
  PaginatedPricingRules,
  CreatePricingRuleRequest,
  UpdatePricingRuleRequest,
  PriceRecommendation,
  PaginatedRecommendations,
  ApproveRecommendationRequest,
  RejectRecommendationRequest,
  PricingSettings,
  UpdatePricingSettingsRequest,
  PricingRecommendationStats,
} from '@/types';

// ============================================
// PRICING RULES
// ============================================

async function getRules(params?: {
  page?: number;
  page_size?: number;
  rule_type?: string;
  is_active?: boolean;
}): Promise<PaginatedPricingRules> {
  return api.get<PaginatedPricingRules>('/api/v1/pricing/rules', params);
}

async function getRuleById(id: string): Promise<PricingRule> {
  return api.get<PricingRule>(`/api/v1/pricing/rules/${id}`);
}

async function createRule(data: CreatePricingRuleRequest): Promise<PricingRule> {
  return api.post<PricingRule>('/api/v1/pricing/rules', data);
}

async function updateRule(id: string, data: UpdatePricingRuleRequest): Promise<PricingRule> {
  return api.patch<PricingRule>(`/api/v1/pricing/rules/${id}`, data);
}

async function deleteRule(id: string): Promise<void> {
  return api.delete<void>(`/api/v1/pricing/rules/${id}`);
}

async function testRule(id: string, productIds?: string[]): Promise<unknown> {
  return api.post(`/api/v1/pricing/rules/${id}/test`, { product_ids: productIds });
}

// ============================================
// RECOMMENDATIONS
// ============================================

async function getRecommendations(params?: {
  page?: number;
  page_size?: number;
  product_id?: string;
  status?: string;
  requires_approval?: boolean;
}): Promise<PaginatedRecommendations> {
  return api.get<PaginatedRecommendations>('/api/v1/pricing/recommendations', params);
}

async function getRecommendationById(id: string): Promise<PriceRecommendation> {
  return api.get<PriceRecommendation>(`/api/v1/pricing/recommendations/${id}`);
}

/**
 * Approve a recommendation
 * 
 * BUG FIX #2: Only send body if data is provided
 * The backend endpoint accepts optional notes but fails validation
 * when receiving an empty object {}
 */
async function approveRecommendation(
  id: string,
  data?: ApproveRecommendationRequest
): Promise<PriceRecommendation> {
  // Only include body if we have actual data to send
  if (data && Object.keys(data).length > 0) {
    return api.post<PriceRecommendation>(
      `/api/v1/pricing/recommendations/${id}/approve`,
      data
    );
  }
  // No body - just POST to the endpoint
  return api.post<PriceRecommendation>(
    `/api/v1/pricing/recommendations/${id}/approve`
  );
}

async function rejectRecommendation(
  id: string,
  data: RejectRecommendationRequest
): Promise<PriceRecommendation> {
  return api.post<PriceRecommendation>(
    `/api/v1/pricing/recommendations/${id}/reject`,
    data
  );
}

/**
 * Apply an approved recommendation to the store
 * 
 * Note: In the updated backend, approve() now also calls apply()
 * automatically. This endpoint is for manual application if needed.
 */
async function applyRecommendation(id: string): Promise<PriceRecommendation> {
  return api.post<PriceRecommendation>(
    `/api/v1/pricing/recommendations/${id}/apply`
  );
}

async function getRecommendationStats(): Promise<PricingRecommendationStats> {
  return api.get<PricingRecommendationStats>('/api/v1/pricing/recommendations/stats');
}

// ============================================
// PRICING SETTINGS
// ============================================

async function getSettings(): Promise<PricingSettings> {
  return api.get<PricingSettings>('/api/v1/pricing/settings');
}

async function updateSettings(data: UpdatePricingSettingsRequest): Promise<PricingSettings> {
  return api.patch<PricingSettings>('/api/v1/pricing/settings', data);
}

// ============================================
// EXPORT AS NAMESPACE
// ============================================

export const pricingApi = {
  // Rules
  getRules,
  getRuleById,
  createRule,
  updateRule,
  deleteRule,
  testRule,

  // Recommendations
  getRecommendations,
  getRecommendationById,
  approveRecommendation,
  rejectRecommendation,
  applyRecommendation,
  getRecommendationStats,

  // Settings
  getSettings,
  updateSettings,
};




