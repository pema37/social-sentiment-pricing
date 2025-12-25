// frontend/lib/hooks/use-payments.ts

/**
 * Payment React Query Hooks
 * 
 * Provides data fetching and mutations for payment features.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getWallet,
  updateWallet,
  removeWallet,
  checkBalance,
  getPlans,
  getSubscription,
  subscribe,
  getPayment,
  getPaymentHistory,
} from '@/lib/api/payments';
import type {
  WalletUpdateRequest,
  SubscriptionTier,
} from '@/types/payment';

// =============================================================================
// Query Keys
// =============================================================================

export const paymentKeys = {
  all: ['payments'] as const,
  wallet: () => [...paymentKeys.all, 'wallet'] as const,
  balance: (address: string) => [...paymentKeys.all, 'balance', address] as const,
  plans: () => [...paymentKeys.all, 'plans'] as const,
  subscription: () => [...paymentKeys.all, 'subscription'] as const,
  payment: (id: string) => [...paymentKeys.all, 'payment', id] as const,
  history: (limit?: number, offset?: number) => 
    [...paymentKeys.all, 'history', { limit, offset }] as const,
};

// =============================================================================
// Wallet Hooks
// =============================================================================

/**
 * Get current user's wallet info
 */
export function useWallet() {
  return useQuery({
    queryKey: paymentKeys.wallet(),
    queryFn: getWallet,
  });
}

/**
 * Update wallet address
 */
export function useUpdateWallet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: WalletUpdateRequest) => updateWallet(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: paymentKeys.wallet() });
    },
  });
}

/**
 * Remove wallet address
 */
export function useRemoveWallet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: removeWallet,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: paymentKeys.wallet() });
    },
  });
}

/**
 * Check balance for any address
 */
export function useCheckBalance(address: string, enabled: boolean = true) {
  return useQuery({
    queryKey: paymentKeys.balance(address),
    queryFn: () => checkBalance(address),
    enabled: enabled && !!address,
  });
}

// =============================================================================
// Subscription Hooks
// =============================================================================

/**
 * Get all available plans
 */
export function usePlans() {
  return useQuery({
    queryKey: paymentKeys.plans(),
    queryFn: getPlans,
    staleTime: 1000 * 60 * 60, // Plans don't change often (1 hour)
  });
}

/**
 * Get current subscription
 */
export function useSubscription() {
  return useQuery({
    queryKey: paymentKeys.subscription(),
    queryFn: getSubscription,
  });
}

/**
 * Subscribe to a plan
 */
export function useSubscribe() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (tier: SubscriptionTier) => subscribe({ tier }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: paymentKeys.subscription() });
      queryClient.invalidateQueries({ queryKey: paymentKeys.history() });
    },
  });
}

// =============================================================================
// Payment Hooks
// =============================================================================

/**
 * Get payment by ID
 */
export function usePayment(paymentId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: paymentKeys.payment(paymentId),
    queryFn: () => getPayment(paymentId),
    enabled: enabled && !!paymentId,
    refetchInterval: (query) => {
      // Poll every 5 seconds if payment is pending
      const payment = query.state.data;
      if (payment?.status === 'pending' || payment?.status === 'processing') {
        return 5000;
      }
      return false;
    },
  });
}

/**
 * Get payment history
 */
export function usePaymentHistory(limit: number = 20, offset: number = 0) {
  return useQuery({
    queryKey: paymentKeys.history(limit, offset),
    queryFn: () => getPaymentHistory(limit, offset),
  });
}
