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
// Tier Configuration (single source of truth)
// =============================================================================

const TIER_CONFIG: Record<string, {
  name: string;
  price: string;
  competitors: number;
  apiCalls: number;
  features: string[];
}> = {
  free: {
    name: 'Free',
    price: '0.00',
    competitors: 0,
    apiCalls: 1000,
    features: ['Up to 5 products', 'Basic sentiment analysis', 'Daily price updates', 'Email support'],
  },
  starter: {
    name: 'Starter',
    price: '29.00',
    competitors: 3,
    apiCalls: 10000,
    features: ['Up to 50 products', 'Advanced sentiment analysis', 'Hourly price updates', 'Competitor tracking (3)', 'Priority email support'],
  },
  professional: {
    name: 'Professional',
    price: '99.00',
    competitors: 10,
    apiCalls: 100000,
    features: ['Up to 500 products', 'Real-time sentiment', 'Real-time price updates', 'Competitor tracking (10)', 'API access', 'Dedicated support'],
  },
  enterprise: {
    name: 'Enterprise',
    price: '299.00',
    competitors: -1,
    apiCalls: -1,
    features: ['Unlimited products', 'Real-time sentiment', 'Real-time price updates', 'Unlimited competitors', 'Full API access', 'Custom integrations', '24/7 support', 'SLA guarantee'],
  },
};

/**
 * Get tier configuration with fallback to free
 */
function getTierConfig(tier: string) {
  return TIER_CONFIG[tier] || TIER_CONFIG.free;
}

/**
 * Transform API subscription response to frontend Subscription type
 */
function transformApiSubscription(apiSub: ApiSubscription): Subscription {
  const config = getTierConfig(apiSub.tier);
  
  return {
    tier: apiSub.tier as SubscriptionTier,
    name: config.name,
    status: apiSub.status as SubscriptionStatus,
    monthly_price: config.price,
    current_period_start: apiSub.current_period_start,
    current_period_end: apiSub.current_period_end,
    limits: {
      products: apiSub.product_limit,
      competitors: config.competitors,
      api_calls: config.apiCalls,
    },
    features: config.features,
  };
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
 */
export async function getPlans(): Promise<PlansResponse> {
  const apiPlans = await api.get<ApiPlan[]>('/api/v1/payments/plans');
  
  const plans: SubscriptionPlan[] = apiPlans.map((plan) => {
    const config = getTierConfig(plan.tier);
    return {
      id: plan.tier as SubscriptionTier,
      name: plan.name,
      monthly_price: (plan.price_monthly ?? 0).toFixed(2),
      products_limit: plan.product_limit,
      competitors_limit: config.competitors,
      api_calls_limit: config.apiCalls,
      features: plan.features,
      popular: plan.tier === 'professional',
    };
  });

  return { plans };
}

/**
 * Get current user's subscription
 */
export async function getSubscription(): Promise<Subscription> {
  const apiSub = await api.get<ApiSubscription>('/api/v1/payments/subscription');
  return transformApiSubscription(apiSub);
}

/**
 * Downgrade current subscription to free tier
 * No payment required - immediately moves user to free plan
 */
export async function downgradeToFree(): Promise<Subscription> {
  const apiSub = await api.post<ApiSubscription>('/api/v1/payments/downgrade-to-free', {});
  return transformApiSubscription(apiSub);
}

/**
 * Subscribe to a plan (creates payment request)
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
    network: data.network || 'bsv',
  });
  
  const isEthereum = (data.network || 'bsv') === 'ethereum';
  
  return {
    payment_id: response.payment_id,
    status: 'pending',
    tier: data.tier,
    amount: response.amount,
    currency: 'MNEE',
    payment_address: response.recipient_address,
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
 * Transform API payment to frontend Payment type
 */
function transformApiPayment(p: ApiPayment): Payment {
  return {
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
  };
}

/**
 * Get payment status by ID
 */
export async function getPayment(paymentId: string): Promise<Payment> {
  const apiPayment = await api.get<ApiPayment>(`/api/v1/payments/payments/${paymentId}`);
  return transformApiPayment(apiPayment);
}

/**
 * Get payment history
 */
export async function getPaymentHistory(
  limit: number = 20,
  offset: number = 0
): Promise<PaymentHistoryResponse> {
  const response = await api.get<{
    payments: ApiPayment[];
    total: number;
    limit: number;
    offset: number;
  }>('/api/v1/payments/history', { limit, offset });

  return {
    payments: response.payments.map(transformApiPayment),
    total: response.total,
    limit: response.limit,
    offset: response.offset,
  };
}

// =============================================================================
// Validation Helpers
// =============================================================================

/**
 * Validate BSV address format (client-side)
 */
export function isValidBsvAddress(address: string): boolean {
  if (!address) return false;
  if (address.startsWith('0x')) return false;
  if (!address.startsWith('1') && !address.startsWith('3')) return false;
  if (address.length < 25 || address.length > 34) return false;
  
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


