// Pricing hooks
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { pricingApi } from '@/lib/api';
import type {
  PricingRule,
  CreatePricingRuleRequest,
  UpdatePricingRuleRequest,
  PriceRecommendation,
  ApproveRecommendationRequest,
  RejectRecommendationRequest,
  PricingSettings,
  UpdatePricingSettingsRequest,
  PricingRecommendationStats,
} from '@/types';

// Re-export types for convenience
export type {
  PricingRule,
  PriceRecommendation,
  PricingSettings,
  PricingRecommendationStats,
  CreatePricingRuleRequest,
  UpdatePricingRuleRequest,
};

// ============================================
// QUERY KEYS
// ============================================

export const pricingKeys = {
  all: ['pricing'] as const,
  
  // Rules
  rules: () => [...pricingKeys.all, 'rules'] as const,
  rulesList: (params?: { page?: number; page_size?: number; rule_type?: string; is_active?: boolean }) =>
    [...pricingKeys.rules(), 'list', params] as const,
  ruleDetail: (id: string) => [...pricingKeys.rules(), 'detail', id] as const,

  // Recommendations
  recommendations: () => [...pricingKeys.all, 'recommendations'] as const,
  recommendationsList: (params?: { page?: number; page_size?: number; status?: string; product_id?: string }) =>
    [...pricingKeys.recommendations(), 'list', params] as const,
  recommendationDetail: (id: string) => [...pricingKeys.recommendations(), 'detail', id] as const,
  recommendationStats: () => [...pricingKeys.recommendations(), 'stats'] as const,

  // Settings
  settings: () => [...pricingKeys.all, 'settings'] as const,
};

// ============================================
// PRICING RULES HOOKS
// ============================================

/** Get paginated pricing rules */
export function usePricingRules(params?: { page?: number; page_size?: number; rule_type?: string; is_active?: boolean }) {
  return useQuery({
    queryKey: pricingKeys.rulesList(params),
    queryFn: () => pricingApi.getRules(params),
    staleTime: 30 * 1000,
  });
}

/** Get single pricing rule */
export function usePricingRule(id: string | null) {
  return useQuery({
    queryKey: pricingKeys.ruleDetail(id || ''),
    queryFn: () => pricingApi.getRuleById(id!),
    enabled: !!id,
    staleTime: 30 * 1000,
  });
}

/** Create pricing rule */
export function useCreatePricingRule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreatePricingRuleRequest) => pricingApi.createRule(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: pricingKeys.rules() });
    },
  });
}

/** Update pricing rule */
export function useUpdatePricingRule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdatePricingRuleRequest }) =>
      pricingApi.updateRule(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: pricingKeys.ruleDetail(variables.id) });
      queryClient.invalidateQueries({ queryKey: pricingKeys.rulesList() });
    },
  });
}

/** Delete pricing rule */
export function useDeletePricingRule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => pricingApi.deleteRule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: pricingKeys.rules() });
    },
  });
}

/** Toggle pricing rule active status */
export function useTogglePricingRule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      pricingApi.updateRule(id, { is_active: isActive }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: pricingKeys.ruleDetail(variables.id) });
      queryClient.invalidateQueries({ queryKey: pricingKeys.rulesList() });
    },
  });
}

// ============================================
// RECOMMENDATION HOOKS
// ============================================

/** Get paginated recommendations */
export function useRecommendations(params?: { page?: number; page_size?: number; status?: string; product_id?: string }) {
  return useQuery({
    queryKey: pricingKeys.recommendationsList(params),
    queryFn: () => pricingApi.getRecommendations(params),
    staleTime: 30 * 1000,
  });
}

/** Get single recommendation */
export function useRecommendation(id: string | null) {
  return useQuery({
    queryKey: pricingKeys.recommendationDetail(id || ''),
    queryFn: () => pricingApi.getRecommendationById(id!),
    enabled: !!id,
    staleTime: 30 * 1000,
  });
}

/** Get pricing recommendation statistics */
export function usePricingRecommendationStats() {
  return useQuery({
    queryKey: pricingKeys.recommendationStats(),
    queryFn: () => pricingApi.getRecommendationStats(),
    staleTime: 60 * 1000,
  });
}

/** Approve recommendation */
export function useApproveRecommendation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data?: ApproveRecommendationRequest }) =>
      pricingApi.approveRecommendation(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendationDetail(variables.id) });
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendationsList() });
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendationStats() });
    },
  });
}

/** Reject recommendation */
export function useRejectRecommendation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: RejectRecommendationRequest }) =>
      pricingApi.rejectRecommendation(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendationDetail(variables.id) });
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendationsList() });
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendationStats() });
    },
  });
}

/** Apply approved recommendation to store */
export function useApplyRecommendation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => pricingApi.applyRecommendation(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendationDetail(id) });
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendationsList() });
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendationStats() });
      // Also invalidate products since prices changed
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });
}

// ============================================
// SETTINGS HOOKS
// ============================================

/** Get pricing settings */
export function usePricingSettings() {
  return useQuery({
    queryKey: pricingKeys.settings(),
    queryFn: () => pricingApi.getSettings(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/** Update pricing settings */
export function useUpdatePricingSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdatePricingSettingsRequest) => pricingApi.updateSettings(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: pricingKeys.settings() });
    },
  });
}
