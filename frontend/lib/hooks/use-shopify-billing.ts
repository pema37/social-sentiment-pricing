// frontend/lib/hooks/use-shopify-billing.ts

/**
 * Shopify Billing Hooks
 *
 * React Query hooks for Shopify-native billing.
 * Mirrors the pattern in use-payments.ts but calls
 * the Shopify billing endpoints instead of MNEE.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getShopifyPlans,
  getShopifyBillingStatus,
  createShopifySubscription,
  changeShopifyPlan,
  cancelShopifySubscription,
  redirectToShopifyBilling,
} from '@/lib/api/shopify-billing';
import type {
  ShopifyPlansListResponse,
  ShopifyBillingStatusResponse,
  ShopifySubscribeRequest,
  ShopifySubscribeResponse,
  ShopifyPlanChangeRequest,
  ShopifyCancelRequest,
  ShopifyCancelResponse,
} from '@/types/payment';

// =============================================================================
// Query Keys
// =============================================================================

export const shopifyBillingKeys = {
  all: ['shopify-billing'] as const,
  plans: () => [...shopifyBillingKeys.all, 'plans'] as const,
  status: (shop?: string) => [...shopifyBillingKeys.all, 'status', shop] as const,
};

// =============================================================================
// Query Hooks
// =============================================================================

/**
 * Fetch available Shopify billing plans.
 * Plans rarely change — long cache time.
 */
export function useShopifyPlans() {
  return useQuery<ShopifyPlansListResponse>({
    queryKey: shopifyBillingKeys.plans(),
    queryFn: () => getShopifyPlans(),
    staleTime: 1000 * 60 * 10, // 10 minutes
  });
}

/**
 * Fetch current Shopify billing status.
 * Queries Shopify's activeSubscriptions for authoritative status.
 */
export function useShopifyBillingStatus(shopDomain?: string) {
  return useQuery<ShopifyBillingStatusResponse>({
    queryKey: shopifyBillingKeys.status(shopDomain),
    queryFn: () => getShopifyBillingStatus(shopDomain),
    staleTime: 1000 * 30, // 30 seconds
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
  });
}

// =============================================================================
// Mutation Hooks
// =============================================================================

/**
 * Create a Shopify subscription.
 * On success, redirects merchant to Shopify's billing approval page.
 */
export function useShopifySubscribe() {
  const queryClient = useQueryClient();

  return useMutation<ShopifySubscribeResponse, Error, ShopifySubscribeRequest>({
    mutationFn: (data) => createShopifySubscription(data),
    onSuccess: (result) => {
      if (result.success && result.confirmation_url) {
        // Redirect merchant to Shopify to approve the charge
        redirectToShopifyBilling(result.confirmation_url);
      }
      queryClient.invalidateQueries({ queryKey: shopifyBillingKeys.all });
    },
  });
}

/**
 * Change Shopify plan (upgrade/downgrade).
 * On success, redirects merchant to approve the new charge.
 */
export function useShopifyChangePlan() {
  const queryClient = useQueryClient();

  return useMutation<ShopifySubscribeResponse, Error, ShopifyPlanChangeRequest>({
    mutationFn: (data) => changeShopifyPlan(data),
    onSuccess: (result) => {
      if (result.success && result.confirmation_url) {
        redirectToShopifyBilling(result.confirmation_url);
      }
      queryClient.invalidateQueries({ queryKey: shopifyBillingKeys.all });
    },
  });
}

/**
 * Cancel the active Shopify subscription.
 */
export function useShopifyCancelSubscription() {
  const queryClient = useQueryClient();

  return useMutation<ShopifyCancelResponse, Error, ShopifyCancelRequest | undefined>({
    mutationFn: (data) => cancelShopifySubscription(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: shopifyBillingKeys.all });
    },
  });
}


