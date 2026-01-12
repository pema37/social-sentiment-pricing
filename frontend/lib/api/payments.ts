// frontend/lib/api/payments.ts

/**
 * Payment API Client
 * 
 * Handles all MNEE payment-related API calls to our backend.
 */

import { api } from './client';
import type {
  WalletInfo,
  WalletUpdateRequest,
  BalanceInfo,
  PlansResponse,
  SubscriptionPlan,
  Subscription,
  SubscribeRequest,
  PaymentRequest,
  Payment,
  PaymentHistoryResponse,
  SubscriptionTier,
  SubscriptionStatus,
  PaymentStatus,
  PaymentType,
} from '@/types/payment';

// =============================================================================
// API Response Types (what the backend actually returns)
// =============================================================================

interface ApiPlan {
  tier: string;
  name: string;
  price_monthly: number;
  price_yearly: number;
  product_limit: number;
  features: string[];
}

interface ApiSubscription {
  tier: string;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  product_limit: number;
  products_used: number;
}

interface ApiPayment {
  id: string;
  amount: string;
  status: string;
  payment_type: string;
  created_at: string;
  transaction_hash: string | null;
}

// =============================================================================
// Wallet Endpoints
// =============================================================================

/**
 * Get current user's wallet info and balance
 */
export async function getWallet(): Promise<WalletInfo> {
  return api.get<WalletInfo>('/api/v1/payments/wallet');
}

/**
 * Update user's BSV wallet address
 */
export async function updateWallet(data: WalletUpdateRequest): Promise<WalletInfo> {
  return api.put<WalletInfo>('/api/v1/payments/wallet', data);
}

/**
 * Remove user's wallet address
 */
export async function removeWallet(): Promise<void> {
  return api.delete<void>('/api/v1/payments/wallet');
}

/**
 * Check balance for any BSV address
 */
export async function checkBalance(address: string): Promise<BalanceInfo> {
  return api.get<BalanceInfo>(`/api/v1/payments/balance/${address}`);
}

// =============================================================================
// Subscription Endpoints
// =============================================================================

/**
 * Get all available subscription plans
 * Transforms API response to match frontend types
 */
export async function getPlans(): Promise<PlansResponse> {
  // API returns array directly, we need to transform it
  const apiPlans = await api.get<ApiPlan[]>('/api/v1/payments/plans');
  
  // Transform to frontend format
  const plans: SubscriptionPlan[] = apiPlans.map((plan) => ({
    id: plan.tier as SubscriptionTier,
    name: plan.name,
    monthly_price: (plan.price_monthly ?? 0).toFixed(2),
    products_limit: plan.product_limit,
    competitors_limit: plan.tier === 'enterprise' ? -1 : plan.tier === 'professional' ? 10 : plan.tier === 'starter' ? 3 : 0,
    api_calls_limit: plan.tier === 'enterprise' ? -1 : plan.tier === 'professional' ? 100000 : plan.tier === 'starter' ? 10000 : 1000,
    features: plan.features,
    popular: plan.tier === 'professional',
  }));

  return { plans };
}

/**
 * Get current user's subscription
 * Transforms API response to match frontend types
 */
export async function getSubscription(): Promise<Subscription> {
  const apiSub = await api.get<ApiSubscription>('/api/v1/payments/subscription');
  
  // Get the plan details for this tier
  const tierPrices: Record<string, string> = {
    free: '0.00',
    starter: '29.00',
    professional: '99.00',
    enterprise: '299.00',
  };

  const tierNames: Record<string, string> = {
    free: 'Free',
    starter: 'Starter',
    professional: 'Professional',
    enterprise: 'Enterprise',
  };

  const tierFeatures: Record<string, string[]> = {
    free: ['Up to 5 products', 'Basic sentiment analysis', 'Daily price updates', 'Email support'],
    starter: ['Up to 50 products', 'Advanced sentiment analysis', 'Hourly price updates', 'Competitor tracking (3)', 'Priority email support'],
    professional: ['Up to 500 products', 'Real-time sentiment', 'Real-time price updates', 'Competitor tracking (10)', 'API access', 'Dedicated support'],
    enterprise: ['Unlimited products', 'Real-time sentiment', 'Real-time price updates', 'Unlimited competitors', 'Full API access', 'Custom integrations', '24/7 support', 'SLA guarantee'],
  };

  return {
    tier: apiSub.tier as SubscriptionTier,
    name: tierNames[apiSub.tier] || apiSub.tier,
    status: apiSub.status as SubscriptionStatus,
    monthly_price: tierPrices[apiSub.tier] || '0.00',
    current_period_start: apiSub.current_period_start,
    current_period_end: apiSub.current_period_end,
    limits: {
      products: apiSub.product_limit,
      competitors: apiSub.tier === 'enterprise' ? -1 : apiSub.tier === 'professional' ? 10 : apiSub.tier === 'starter' ? 3 : 0,
      api_calls: apiSub.tier === 'enterprise' ? -1 : apiSub.tier === 'professional' ? 100000 : apiSub.tier === 'starter' ? 10000 : 1000,
    },
    features: tierFeatures[apiSub.tier] || [],
  };
}

/**
 * Subscribe to a plan (creates payment request)
 * Updated to support network parameter for Ethereum/BSV selection
 */
export async function subscribe(data: SubscribeRequest): Promise<PaymentRequest> {
  const response = await api.post<{
    payment_id: string;
    amount: string;
    recipient_address: string;
    memo: string;
    expires_at: string;
    network: string;
  }>('/api/v1/payments/subscribe', {
    tier: data.tier,
    billing_cycle: 'monthly',
    network: data.network || 'bsv',  // Send network to backend!
  });
  
  // Instructions differ based on network
  const isEthereum = (data.network || 'bsv') === 'ethereum';
  
  // Transform response to match frontend type
  return {
    payment_id: response.payment_id,
    status: 'pending',
    tier: data.tier,
    amount: response.amount,
    currency: 'MNEE',
    payment_address: response.recipient_address,  // Now correct for network!
    memo: response.memo,
    expires_at: response.expires_at,
    instructions: isEthereum
      ? {
          step1: 'Click "Pay" to open MetaMask',
          step2: `Confirm sending ${response.amount} MNEE`,
          step3: 'Wait for transaction confirmation',
          step4: 'Your subscription will activate automatically',
        }
      : {
          step1: 'Open your BSV wallet (HandCash or RelayX)',
          step2: `Send exactly ${response.amount} MNEE to the address above`,
          step3: `Include memo: ${response.memo}`,
          step4: 'Wait for confirmation (usually < 1 minute)',
        },
  };
}

// =============================================================================
// Payment Endpoints
// =============================================================================

/**
 * Get payment status by ID
 */
export async function getPayment(paymentId: string): Promise<Payment> {
  const apiPayment = await api.get<ApiPayment>(`/api/v1/payments/payments/${paymentId}`);
  
  return {
    id: apiPayment.id,
    user_id: '',
    subscription_id: null,
    amount: apiPayment.amount,
    amount_raw: parseFloat(apiPayment.amount) * 100000,
    currency: 'MNEE',
    status: apiPayment.status as PaymentStatus,
    payment_type: apiPayment.payment_type as PaymentType,
    txid: apiPayment.transaction_hash,
    from_address: null,
    to_address: null,
    memo: null,
    description: null,
    created_at: apiPayment.created_at,
    updated_at: apiPayment.created_at,
    expires_at: null,
    confirmed_at: null,
  };
}

/**
 * Get payment history
 */
export async function getPaymentHistory(
  limit: number = 20,
  offset: number = 0
): Promise<PaymentHistoryResponse> {
  const apiPayments = await api.get<ApiPayment[]>('/api/v1/payments/history', { limit, offset });
  
  const payments: Payment[] = apiPayments.map((p) => ({
    id: p.id,
    user_id: '',
    subscription_id: null,
    amount: p.amount,
    amount_raw: parseFloat(p.amount) * 100000,
    currency: 'MNEE',
    status: p.status as PaymentStatus,
    payment_type: p.payment_type as PaymentType,
    txid: p.transaction_hash,
    from_address: null,
    to_address: null,
    memo: null,
    description: null,
    created_at: p.created_at,
    updated_at: p.created_at,
    expires_at: null,
    confirmed_at: null,
  }));

  return {
    payments,
    total: payments.length,
    limit,
    offset,
  };
}

// =============================================================================
// Validation Helpers
// =============================================================================

/**
 * Validate BSV address format (client-side)
 */
export function isValidBsvAddress(address: string): boolean {
  // BSV addresses start with 1 or 3, are 25-34 characters
  if (!address) return false;
  
  // Reject Ethereum addresses
  if (address.startsWith('0x')) return false;
  
  // Check BSV format
  if (!address.startsWith('1') && !address.startsWith('3')) return false;
  
  // Check length
  if (address.length < 25 || address.length > 34) return false;
  
  // Base58 characters (no 0, O, I, l)
  const base58Regex = /^[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]+$/;
  return base58Regex.test(address);
}

/**
 * Format MNEE amount for display
 */
export function formatMneeAmount(amount: string | number): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '0.00 MNEE';
  return `${num.toFixed(2)} MNEE`;
}

/**
 * Format USD equivalent
 */
export function formatUsdAmount(amount: string | number): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '$0.00 USD';
  return `$${num.toFixed(2)} USD`;
}

