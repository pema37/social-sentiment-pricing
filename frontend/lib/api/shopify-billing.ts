// frontend/lib/api/shopify-billing.ts

/**
 * Shopify Billing API Client
 *
 * Handles Shopify-native billing API calls. These are separate from the
 * MNEE payment endpoints and only used when the app is installed via
 * the Shopify App Store.
 *
 * Detection: check for ?shop= or ?host= URL params, or window.shopify
 */

import { api } from './client';
import type {
  ShopifyPlansListResponse,
  ShopifySubscribeRequest,
  ShopifySubscribeResponse,
  ShopifyBillingStatusResponse,
  ShopifyBillingCallbackResponse,
  ShopifyPlanChangeRequest,
  ShopifyCancelRequest,
  ShopifyCancelResponse,
} from '@/types/payment';

// Re-export types so hooks can import from here or from @/types/payment
export type {
  ShopifyPlansListResponse,
  ShopifySubscribeRequest,
  ShopifySubscribeResponse,
  ShopifyBillingStatusResponse,
  ShopifyBillingCallbackResponse,
  ShopifyPlanChangeRequest,
  ShopifyCancelRequest,
  ShopifyCancelResponse,
  ShopifyPlanInfo,
} from '@/types/payment';

// Shopify App Bridge global type
declare global {
  interface Window {
    shopify?: {
      redirectExternal?: (url: string) => void;
    };
  }
}

// =============================================================================
// Verify Request Type
// =============================================================================

export interface ShopifyVerifyRequest {
  charge_id: string;
  shop_domain?: string | null;
}

// =============================================================================
// API Functions
// =============================================================================

const BILLING_BASE = '/api/v1/integrations/shopify/billing';

/**
 * Get available Shopify billing plans.
 * No auth required — can be called from embedded app before login.
 */
export async function getShopifyPlans(): Promise<ShopifyPlansListResponse> {
  return api.get<ShopifyPlansListResponse>(`${BILLING_BASE}/plans`);
}

/**
 * Create a Shopify subscription. Returns a confirmation_url to redirect
 * the merchant to Shopify's approval page.
 */
export async function createShopifySubscription(
  data: ShopifySubscribeRequest
): Promise<ShopifySubscribeResponse> {
  return api.post<ShopifySubscribeResponse>(`${BILLING_BASE}/subscribe`, data);
}

/**
 * Verify a Shopify charge after merchant approval.
 * Called when the billing page loads with ?charge_id= in the URL.
 */
export async function verifyShopifyCharge(
  data: ShopifyVerifyRequest
): Promise<ShopifyBillingCallbackResponse> {
  return api.post<ShopifyBillingCallbackResponse>(`${BILLING_BASE}/verify`, data);
}

/**
 * Check the current Shopify billing status.
 * Queries Shopify's activeSubscriptions for authoritative status.
 */
export async function getShopifyBillingStatus(
  shopDomain?: string
): Promise<ShopifyBillingStatusResponse> {
  const params = shopDomain ? { shop_domain: shopDomain } : {};
  return api.get<ShopifyBillingStatusResponse>(`${BILLING_BASE}/status`, params);
}

/**
 * Change Shopify plan (upgrade/downgrade).
 * Returns a new confirmation_url — merchant must approve the change.
 */
export async function changeShopifyPlan(
  data: ShopifyPlanChangeRequest
): Promise<ShopifySubscribeResponse> {
  return api.post<ShopifySubscribeResponse>(`${BILLING_BASE}/change-plan`, data);
}

/**
 * Cancel the active Shopify subscription.
 */
export async function cancelShopifySubscription(
  data?: ShopifyCancelRequest
): Promise<ShopifyCancelResponse> {
  return api.post<ShopifyCancelResponse>(`${BILLING_BASE}/cancel`, data || {});
}

// =============================================================================
// Shopify Context Detection Helpers
// =============================================================================

/**
 * Check if we're running inside the Shopify Admin (embedded app).
 * Returns the shop domain if embedded, null otherwise.
 */
export function getShopifyContext(): {
  isShopify: boolean;
  shop: string | null;
  host: string | null;
} {
  if (typeof window === 'undefined') {
    return { isShopify: false, shop: null, host: null };
  }

  const params = new URLSearchParams(window.location.search);
  const shop = params.get('shop');
  const host = params.get('host');

  // Check URL params first (most reliable)
  if (shop) {
    return { isShopify: true, shop, host };
  }

  // Check if Shopify App Bridge is loaded
  const hasAppBridge = !!window.shopify;
  if (hasAppBridge) {
    return { isShopify: true, shop: null, host: null };
  }

  return { isShopify: false, shop: null, host: null };
}

/**
 * Redirect to Shopify's billing approval page.
 * In embedded mode, uses Shopify's redirect. Otherwise, window.location.
 */
export function redirectToShopifyBilling(confirmationUrl: string): void {
  if (typeof window === 'undefined') return;

  // If embedded in Shopify Admin, use App Bridge redirect
  const shopify = window.shopify;
  if (shopify?.redirectExternal) {
    shopify.redirectExternal(confirmationUrl);
    return;
  }

  // Fallback: top-level redirect (breaks out of iframe)
  if (window.top !== window.self) {
    window.top?.location.assign(confirmationUrl);
  } else {
    window.location.assign(confirmationUrl);
  }
}

