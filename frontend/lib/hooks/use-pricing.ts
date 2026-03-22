// Pricing hooks
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { pricingApi } from '@/lib/api';
import { toast } from '@/lib/hooks/use-toast';
import { pricingKeys, productKeys } from '@/lib/api/query-keys';
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

// Re-export keys for backwards compatibility
export { pricingKeys };

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
      toast.success({ title: 'Rule created', message: 'Pricing rule has been created successfully' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to create rule', message: error.message });
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
      queryClient.invalidateQueries({ queryKey: pricingKeys.rules() });
      toast.success({ title: 'Rule updated', message: 'Pricing rule has been updated successfully' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to update rule', message: error.message });
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
      toast.success({ title: 'Rule deleted', message: 'Pricing rule has been deleted' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to delete rule', message: error.message });
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
      queryClient.invalidateQueries({ queryKey: pricingKeys.rules() });
      toast.success({ 
        title: variables.isActive ? 'Rule activated' : 'Rule deactivated',
        message: `Pricing rule has been ${variables.isActive ? 'activated' : 'deactivated'}`,
      });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to update rule', message: error.message });
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

/**
 * Approve recommendation
 * 
 * BUG FIX #2: Added invalidation for product queries since approval
 * now triggers price push to e-commerce platform in the backend.
 * This ensures the product detail page shows the updated price.
 */
export function useApproveRecommendation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data?: ApproveRecommendationRequest }) =>
      pricingApi.approveRecommendation(id, data),
    onSuccess: (response, variables) => {
      // Invalidate recommendation queries
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendationDetail(variables.id) });
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendations() });
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendationStats() });
      
      // Invalidate specific product queries since price may have changed
      if (response?.product_id) {
        queryClient.invalidateQueries({ queryKey: productKeys.detail(response.product_id) });
        queryClient.invalidateQueries({ queryKey: productKeys.priceHistory(response.product_id) });
        queryClient.invalidateQueries({ queryKey: productKeys.lists() });
      }
      
      // Check if price was actually applied (status = 'applied')
      const wasApplied = response?.status === 'applied';
      
      toast.success({ 
        title: wasApplied ? 'Price updated!' : 'Recommendation approved', 
        message: wasApplied 
          ? 'The new price has been applied to your store' 
          : 'You can now apply this price change'
      });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to approve', message: error.message });
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
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendations() });
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendationStats() });
      toast.success({ title: 'Recommendation rejected', message: 'The recommendation has been rejected' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to reject', message: error.message });
    },
  });
}

/**
 * Apply approved recommendation to store
 * 
 * This is a separate step from approval - use when approval doesn't
 * automatically push to the store.
 */
export function useApplyRecommendation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => pricingApi.applyRecommendation(id),
    onSuccess: (response, id) => {
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendationDetail(id) });
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendations() });
      queryClient.invalidateQueries({ queryKey: pricingKeys.recommendationStats() });
      
      // Invalidate all product queries since prices changed
      queryClient.invalidateQueries({ queryKey: productKeys.all });
      
      // If we have the product_id from response, invalidate that specific product
      if (response?.product_id) {
        queryClient.invalidateQueries({ queryKey: productKeys.detail(response.product_id) });
        queryClient.invalidateQueries({ queryKey: productKeys.priceHistory(response.product_id) });
      }
      
      toast.success({ title: 'Price updated!', message: 'The new price has been applied to your store' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to apply price', message: error.message });
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
    staleTime: 5 * 60 * 1000,
  });
}

/** Update pricing settings */
export function useUpdatePricingSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdatePricingSettingsRequest) => pricingApi.updateSettings(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: pricingKeys.settings() });
      toast.success({ title: 'Settings saved', message: 'Your pricing settings have been updated' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to save settings', message: error.message });
    },
  });
}




