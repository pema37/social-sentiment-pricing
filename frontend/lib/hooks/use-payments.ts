// frontend/lib/hooks/use-payments.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getWallet,
  updateWallet,
  checkBalance,
  getPlans,
  getSubscription,
  subscribe,
  getPayment,
  getPaymentHistory,
  downgradeToFree,
} from '@/lib/api/payments';
import type {
  Subscription,
  WalletInfo,
  BalanceInfo,
  Payment,
  PaymentRequest,
  SubscribeRequest,
  WalletUpdateRequest,
  PlansResponse,
} from '@/types/payment';

// Query keys for React Query
export const paymentKeys = {
  all: ['payments'] as const,
  wallet: () => [...paymentKeys.all, 'wallet'] as const,
  balance: (address: string) => [...paymentKeys.all, 'balance', address] as const,
  subscription: () => [...paymentKeys.all, 'subscription'] as const,
  plans: () => [...paymentKeys.all, 'plans'] as const,
  history: (params?: { limit?: number; offset?: number }) => 
    [...paymentKeys.all, 'history', params] as const,
  payment: (id: string) => [...paymentKeys.all, 'payment', id] as const,
};

// ============================================
// SUBSCRIPTION HOOKS
// ============================================

/**
 * Fetch current user subscription
 * Uses aggressive cache invalidation to ensure fresh data
 */
export function useSubscription() {
  return useQuery<Subscription>({
    queryKey: paymentKeys.subscription(),
    queryFn: () => getSubscription(),
    // Subscription data should be fresh - admin upgrades need to reflect immediately
    staleTime: 1000 * 30, // 30 seconds
    refetchOnMount: 'always', // Always refetch when component mounts
    refetchOnWindowFocus: true, // Refetch when user returns to tab
    refetchOnReconnect: true, // Refetch when network reconnects
  });
}

/**
 * Fetch available subscription plans
 * Plans rarely change, so longer cache is fine
 */
export function usePlans() {
  return useQuery<PlansResponse>({
    queryKey: paymentKeys.plans(),
    queryFn: () => getPlans(),
    staleTime: 1000 * 60 * 10, // 10 minutes - plans don't change often
  });
}

// ============================================
// WALLET HOOKS
// ============================================

/**
 * Fetch user wallet info
 */
export function useWallet() {
  return useQuery<WalletInfo>({
    queryKey: paymentKeys.wallet(),
    queryFn: () => getWallet(),
    staleTime: 1000 * 60, // 1 minute
  });
}

/**
 * Fetch balance for a specific address
 */
export function useBalance(address: string | null | undefined) {
  return useQuery<BalanceInfo>({
    queryKey: paymentKeys.balance(address || ''),
    queryFn: () => checkBalance(address!),
    enabled: !!address,
    staleTime: 1000 * 30, // 30 seconds - balances can change
    refetchInterval: 1000 * 60, // Auto-refresh every minute
  });
}

/**
 * Update wallet address mutation
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

// ============================================
// PAYMENT HOOKS
// ============================================

/**
 * Fetch payment history
 */
export function usePaymentHistory(params?: { limit?: number; offset?: number }) {
  return useQuery<{ payments: Payment[]; total: number }>({
    queryKey: paymentKeys.history(params),
    queryFn: () => getPaymentHistory(params?.limit, params?.offset),
    staleTime: 1000 * 60, // 1 minute
  });
}

/**
 * Fetch single payment by ID
 */
export function usePayment(paymentId: string | null | undefined) {
  return useQuery<Payment>({
    queryKey: paymentKeys.payment(paymentId || ''),
    queryFn: () => getPayment(paymentId!),
    enabled: !!paymentId,
    staleTime: 1000 * 30, // 30 seconds
  });
}

/**
 * Subscribe to a plan (initiates payment)
 */
export function useSubscribe() {
  const queryClient = useQueryClient();
  
  return useMutation<PaymentRequest, Error, SubscribeRequest>({
    mutationFn: (data) => subscribe(data),
    onSuccess: () => {
      // Invalidate history since a new pending payment was created
      queryClient.invalidateQueries({ queryKey: paymentKeys.history() });
    },
  });
}

/**
 * Downgrade to free tier
 */
export function useDowngradeToFree() {
  const queryClient = useQueryClient();
  
  return useMutation<Subscription, Error, void>({
    mutationFn: () => downgradeToFree(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: paymentKeys.subscription() });
      queryClient.invalidateQueries({ queryKey: paymentKeys.history() });
    },
  });
}

// ============================================
// UTILITY HOOKS
// ============================================

/**
 * Hook to manually invalidate subscription cache
 * Useful when you know the subscription has been updated externally
 */
export function useInvalidateSubscription() {
  const queryClient = useQueryClient();
  
  return () => {
    queryClient.invalidateQueries({ queryKey: paymentKeys.subscription() });
    queryClient.refetchQueries({ queryKey: paymentKeys.subscription() });
  };
}

/**
 * Hook to invalidate all payment-related caches
 */
export function useInvalidateAllPayments() {
  const queryClient = useQueryClient();
  
  return () => {
    queryClient.invalidateQueries({ queryKey: paymentKeys.all });
  };
}



