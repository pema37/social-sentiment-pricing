// frontend/lib/api/pricing.ts
// API functions for pricing rules, recommendations, and settings
//
// FIX (2026-01-27): Added structured error handling for approval endpoints

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
  ApprovalErrorDetail,
} from '@/types';

// ============================================
// ERROR HANDLING
// ============================================

/**
 * Custom error class for approval failures
 * Contains structured error info from backend
 */
export class ApprovalError extends Error {
  code: string;
  suggestion: string;

  constructor(detail: ApprovalErrorDetail) {
    super(detail.message);
    this.name = 'ApprovalError';
    this.code = detail.error_code;
    this.suggestion = detail.suggestion;
  }
}

/**
 * Parse error response and extract structured details if available
 */
function parseApprovalError(error: unknown): ApprovalError | Error {
  // Check if it's an API error with structured detail
  if (error && typeof error === 'object') {
    const err = error as { detail?: ApprovalErrorDetail | string; message?: string };
    
    // Backend returns { detail: { message, error_code, suggestion } }
    if (err.detail && typeof err.detail === 'object') {
      const detail = err.detail as ApprovalErrorDetail;
      if (detail.message && detail.error_code) {
        return new ApprovalError(detail);
      }
    }
    
    // Fallback: detail is just a string
    if (err.detail && typeof err.detail === 'string') {
      return new Error(err.detail);
    }
    
    // Fallback: message property
    if (err.message) {
      return new Error(err.message);
    }
  }
  
  // Unknown error format
  if (error instanceof Error) {
    return error;
  }
  
  return new Error('An unexpected error occurred');
}

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
 * FIX (2026-01-27): Now throws ApprovalError with structured error info
 * including error_code and suggestion for better UX
 * 
 * @throws {ApprovalError} When approval fails with structured error
 * @throws {Error} When approval fails with generic error
 */
async function approveRecommendation(
  id: string,
  data?: ApproveRecommendationRequest
): Promise<PriceRecommendation> {
  try {
    // Only include body if we have actual data to send
    if (data && Object.keys(data).length > 0) {
      return await api.post<PriceRecommendation>(
        `/api/v1/pricing/recommendations/${id}/approve`,
        data
      );
    }
    // No body - just POST to the endpoint
    return await api.post<PriceRecommendation>(
      `/api/v1/pricing/recommendations/${id}/approve`
    );
  } catch (error) {
    throw parseApprovalError(error);
  }
}

/**
 * Reject a recommendation
 * 
 * @throws {ApprovalError} When rejection fails with structured error
 */
async function rejectRecommendation(
  id: string,
  data: RejectRecommendationRequest
): Promise<PriceRecommendation> {
  try {
    return await api.post<PriceRecommendation>(
      `/api/v1/pricing/recommendations/${id}/reject`,
      data
    );
  } catch (error) {
    throw parseApprovalError(error);
  }
}

/**
 * Apply an approved recommendation to the store
 * 
 * Note: In the updated backend, approve() now also calls apply()
 * automatically. This endpoint is for manual application if needed.
 * 
 * @throws {ApprovalError} When application fails with structured error
 */
async function applyRecommendation(id: string): Promise<PriceRecommendation> {
  try {
    return await api.post<PriceRecommendation>(
      `/api/v1/pricing/recommendations/${id}/apply`
    );
  } catch (error) {
    throw parseApprovalError(error);
  }
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

// Export error utilities for use in components
export { parseApprovalError };




