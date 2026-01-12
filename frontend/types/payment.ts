// Payment and Subscription Types
// AUTO-SYNCED with backend via openapi-typescript
// Last synced: 2026-01-08
// Source: components["schemas"]["PaymentInfo"], SubscriptionInfo, etc.

// ============================================
// ENUMS / UNION TYPES
// ============================================

export type PaymentStatus = 
  | 'pending' 
  | 'processing' 
  | 'confirmed' 
  | 'failed' 
  | 'expired' 
  | 'refunded';

export type PaymentType = 
  | 'subscription' 
  | 'one_time' 
  | 'refund';

export type SubscriptionTier = 
  | 'free' 
  | 'starter' 
  | 'professional' 
  | 'enterprise';

export type SubscriptionStatus = 
  | 'active' 
  | 'inactive' 
  | 'past_due' 
  | 'cancelled' 
  | 'trialing';

// ============================================
// WALLET TYPES
// ============================================

/**
 * Wallet info response
 * Matches: components["schemas"]["WalletInfo"]
 */
export interface WalletInfo {
  bsv_wallet_address: string | null;
  balance: string | null;
  balance_raw: number | null;
}

/**
 * Wallet update request
 * Matches: components["schemas"]["WalletUpdateRequest"]
 */
export interface WalletUpdateRequest {
  bsv_wallet_address: string;
}

/**
 * Balance info response
 * Matches: components["schemas"]["BalanceInfo"]
 */
export interface BalanceInfo {
  address: string;
  balance: string;
  balance_raw: number;
}

// ============================================
// SUBSCRIPTION PLAN TYPES
// ============================================

/**
 * Subscription plan info
 * Matches: components["schemas"]["PlanInfo"]
 */
export interface SubscriptionPlan {
  id: SubscriptionTier;
  name: string;
  monthly_price: string;
  products_limit: number;
  competitors_limit: number;
  api_calls_limit: number;
  features: string[];
  popular?: boolean;
}

/**
 * Current subscription info
 * Matches: components["schemas"]["SubscriptionInfo"]
 */
export interface Subscription {
  tier: SubscriptionTier;
  name: string;
  status: SubscriptionStatus;
  monthly_price: string;
  current_period_start: string | null;
  current_period_end: string | null;
  limits: {
    products: number;
    competitors: number;
    api_calls: number;
  };
  features: string[];
}

// ============================================
// PAYMENT REQUEST TYPES
// ============================================

/**
 * Subscribe request
 * Matches: components["schemas"]["SubscribeRequest"]
 */
export interface SubscribeRequest {
  tier: SubscriptionTier;
  network?: 'ethereum' | 'bsv';
}

/**
 * Payment request response (for payment initiation)
 * Matches: components["schemas"]["PaymentRequest"]
 */
export interface PaymentRequest {
  payment_id: string;
  status: string;
  tier: SubscriptionTier;
  amount: string;
  currency: string;
  payment_address: string;
  memo: string;
  expires_at: string;
  instructions: {
    step1: string;
    step2: string;
    step3: string;
    step4: string;
  };
}

/**
 * Confirm payment request
 * Matches: components["schemas"]["ConfirmPaymentRequest"]
 */
export interface ConfirmPaymentRequest {
  txid: string;
}

/**
 * Confirm payment response
 * Matches: components["schemas"]["ConfirmPaymentResponse"]
 */
export interface ConfirmPaymentResponse {
  success: boolean;
  message: string;
  payment_id: string;
  new_tier: SubscriptionTier | null;
}

// ============================================
// PAYMENT RECORD TYPES
// ============================================

/**
 * Payment info response
 * Matches: components["schemas"]["PaymentInfo"]
 */
export interface Payment {
  id: string;
  user_id: string;
  subscription_id: string | null;
  amount: string;
  amount_raw: number;
  currency: string;
  status: PaymentStatus;
  payment_type: PaymentType;
  txid: string | null;
  from_address: string | null;
  to_address: string | null;
  memo: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
  expires_at: string | null;
  confirmed_at: string | null;
}

/**
 * Payment history response (array of payments)
 */
export interface PaymentHistoryResponse {
  payments: Payment[];
  total: number;
  limit: number;
  offset: number;
}

// ============================================
// WEBHOOK TYPES
// ============================================

/**
 * Webhook response
 * Matches: components["schemas"]["WebhookResponse"]
 */
export interface WebhookResponse {
  status: string;
  message: string;
}

// ============================================
// UI HELPERS (Frontend-only)
// ============================================

export const TIER_DISPLAY_NAMES: Record<SubscriptionTier, string> = {
  free: 'Free',
  starter: 'Starter',
  professional: 'Professional',
  enterprise: 'Enterprise',
};

export const STATUS_COLORS: Record<PaymentStatus, string> = {
  pending: 'yellow',
  processing: 'blue',
  confirmed: 'green',
  failed: 'red',
  expired: 'gray',
  refunded: 'purple',
};

export const SUBSCRIPTION_STATUS_COLORS: Record<SubscriptionStatus, string> = {
  active: 'green',
  inactive: 'gray',
  past_due: 'yellow',
  cancelled: 'red',
  trialing: 'blue',
};

export interface PlansResponse {
  plans: SubscriptionPlan[];
}
