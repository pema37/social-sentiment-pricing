// frontend/lib/api/shopify-billing.ts

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

export interface ShopifyVerifyRequest {
  charge_id: string;
  shop_domain?: string | null;
}

const BILLING_BASE = '/api/v1/integrations/shopify/billing';

export async function getShopifyPlans(): Promise<ShopifyPlansListResponse> {
  return api.get<ShopifyPlansListResponse>(`${BILLING_BASE}/plans`);
}

export async function createShopifySubscription(
  data: ShopifySubscribeRequest
): Promise<ShopifySubscribeResponse> {
  return api.post<ShopifySubscribeResponse>(`${BILLING_BASE}/subscribe`, data);
}

export async function verifyShopifyCharge(
  data: ShopifyVerifyRequest
): Promise<ShopifyBillingCallbackResponse> {
  return api.post<ShopifyBillingCallbackResponse>(`${BILLING_BASE}/verify`, data);
}

export async function getShopifyBillingStatus(
  shopDomain?: string
): Promise<ShopifyBillingStatusResponse> {
  const params = shopDomain ? { shop_domain: shopDomain } : {};
  return api.get<ShopifyBillingStatusResponse>(`${BILLING_BASE}/status`, params);
}

export async function changeShopifyPlan(
  data: ShopifyPlanChangeRequest
): Promise<ShopifySubscribeResponse> {
  return api.post<ShopifySubscribeResponse>(`${BILLING_BASE}/change-plan`, data);
}

export async function cancelShopifySubscription(
  data?: ShopifyCancelRequest
): Promise<ShopifyCancelResponse> {
  return api.post<ShopifyCancelResponse>(`${BILLING_BASE}/cancel`, data || {});
}

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

  if (shop) {
    return { isShopify: true, shop, host };
  }

  const hasAppBridge = !!window.shopify;
  if (hasAppBridge) {
    return { isShopify: true, shop: null, host: null };
  }

  return { isShopify: false, shop: null, host: null };
}

export function redirectToShopifyBilling(confirmationUrl: string): void {
  if (typeof window === 'undefined') return;

  const shopify = window.shopify as unknown as { redirectExternal?: (url: string) => void } | undefined;
  if (typeof shopify?.redirectExternal === 'function') {
    shopify.redirectExternal(confirmationUrl);
    return;
  }

  if (window.top !== window.self) {
    window.top?.location.assign(confirmationUrl);
  } else {
    window.location.assign(confirmationUrl);
  }
}


