// frontend/types/payment.ts

/**
 * Payment and Subscription Types for MNEE BSV Integration
 */

// =============================================================================
// Enums
// =============================================================================

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

// =============================================================================
// Wallet
// =============================================================================

export interface WalletInfo {
  bsv_wallet_address: string | null;
  balance: string | null;
  balance_raw: number | null;
}

export interface WalletUpdateRequest {
  bsv_wallet_address: string;
}

export interface BalanceInfo {
  address: string;
  balance: string;
  balance_raw: number;
}

// =============================================================================
// Subscription Plans
// =============================================================================

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

export interface PlansResponse {
  plans: SubscriptionPlan[];
}

// =============================================================================
// Current Subscription
// =============================================================================

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

// =============================================================================
// Payment Request (Subscribe)
// =============================================================================

export interface SubscribeRequest {
  tier: SubscriptionTier;
}

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

// =============================================================================
// Payment Records
// =============================================================================

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

export interface PaymentHistoryResponse {
  payments: Payment[];
  total: number;
  limit: number;
  offset: number;
}

// =============================================================================
// Helpers
// =============================================================================

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
