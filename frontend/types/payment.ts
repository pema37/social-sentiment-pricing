// Payment and Subscription Types
// AUTO-SYNCED with backend via openapi-typescript
// Last synced: 2026-03-27
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
  bsv_wallet_address: string | null;
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
// SHOPIFY BILLING TYPES (2026-03-27)
// Matches: backend/schemas/shopify_billing.py
// ============================================

export type ShopifyBillingTier = 'free' | 'starter' | 'professional';

/**
 * Shopify plan info for display
 * Matches: components["schemas"]["ShopifyPlanInfo"]
 */
export interface ShopifyPlanInfo {
  tier: string;
  name: string;
  price_monthly: number;
  trial_days: number;
  product_limit: number;
  features: string[];
}

/**
 * Shopify plans list response
 * Matches: components["schemas"]["ShopifyPlansListResponse"]
 */
export interface ShopifyPlansListResponse {
  plans: ShopifyPlanInfo[];
}

/**
 * Shopify subscribe request
 * Matches: components["schemas"]["ShopifySubscribeRequest"]
 */
export interface ShopifySubscribeRequest {
  tier: ShopifyBillingTier;
  shop_domain?: string | null;
}

/**
 * Shopify subscribe response
 * Matches: components["schemas"]["ShopifySubscribeResponse"]
 */
export interface ShopifySubscribeResponse {
  success: boolean;
  confirmation_url: string | null;
  shopify_subscription_id: string | null;
  tier: string;
  message: string;
}

/**
 * Shopify billing callback/verify response
 * Matches: components["schemas"]["ShopifyBillingCallbackResponse"]
 */
export interface ShopifyBillingCallbackResponse {
  success: boolean;
  status: string;
  tier: string | null;
  message: string;
}

/**
 * Shopify billing status response
 * Matches: components["schemas"]["ShopifyBillingStatusResponse"]
 */
export interface ShopifyBillingStatusResponse {
  has_active_subscription: boolean;
  tier: string | null;
  plan_name: string | null;
  status: string | null;
  shopify_subscription_id: string | null;
  trial_days: number | null;
  current_period_end: string | null;
  test: boolean;
  price: string | null;
  currency: string | null;
}

/**
 * Shopify plan change request
 * Matches: components["schemas"]["ShopifyPlanChangeRequest"]
 */
export interface ShopifyPlanChangeRequest {
  new_tier: ShopifyBillingTier;
  shop_domain?: string | null;
}

/**
 * Shopify cancel request
 * Matches: components["schemas"]["ShopifyCancelRequest"]
 */
export interface ShopifyCancelRequest {
  prorate?: boolean;
  shop_domain?: string | null;
}

/**
 * Shopify cancel response
 * Matches: components["schemas"]["ShopifyCancelResponse"]
 */
export interface ShopifyCancelResponse {
  success: boolean;
  message: string;
  status: string | null;
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

