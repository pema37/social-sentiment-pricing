// frontend/lib/domain/integrations.ts
// Domain layer: Transforms between form data and API shapes
// Single place to fix when API changes - components don't know API details

import { z } from 'zod';
import type { 
  Integration,
  IntegrationUpdate,
  WooCommerceConnectRequest,
  OAuthInitRequest,
  ProductLinkCreate,
  EcommercePlatform,
} from '@/types/integration';

// ============================================
// ZOD SCHEMAS
// ============================================

/**
 * URL validation - required and must be valid
 */
const requiredUrl = z.string()
  .min(1, 'Store URL is required')
  .refine((val) => {
    try {
      new URL(val.startsWith('http') ? val : `https://${val}`);
      return true;
    } catch {
      return false;
    }
  }, { message: 'Must be a valid URL' });

/**
 * WooCommerce connection form schema
 */
export const wooCommerceConnectSchema = z.object({
  store_url: requiredUrl,
  store_name: z.string(),
  consumer_key: z.string().min(1, 'Consumer key is required'),
  consumer_secret: z.string().min(1, 'Consumer secret is required'),
});

/**
 * Shopify OAuth init form schema
 */
export const shopifyConnectSchema = z.object({
  store_url: requiredUrl,
});

/**
 * Integration settings update schema
 */
export const integrationUpdateSchema = z.object({
  store_name: z.string(),
  is_paused: z.boolean(),
});

/**
 * Product link form schema
 */
export const productLinkSchema = z.object({
  product_id: z.string().min(1, 'Select a product'),
  external_product_id: z.string().min(1, 'External product ID is required'),
  external_variant_id: z.string(),
});

// ============================================
// TYPES
// ============================================

export type WooCommerceConnectFormData = z.input<typeof wooCommerceConnectSchema>;
export type WooCommerceConnectFormErrors = Partial<Record<keyof WooCommerceConnectFormData, string>>;

export type ShopifyConnectFormData = z.input<typeof shopifyConnectSchema>;
export type ShopifyConnectFormErrors = Partial<Record<keyof ShopifyConnectFormData, string>>;

export type IntegrationUpdateFormData = z.input<typeof integrationUpdateSchema>;
export type IntegrationUpdateFormErrors = Partial<Record<keyof IntegrationUpdateFormData, string>>;

export type ProductLinkFormData = z.input<typeof productLinkSchema>;
export type ProductLinkFormErrors = Partial<Record<keyof ProductLinkFormData, string>>;

// ============================================
// UTILITIES
// ============================================

/**
 * Normalize store URL - ensure https and clean format
 */
export function normalizeStoreUrl(url: string): string {
  let cleaned = url.trim().toLowerCase();
  
  // Remove trailing slashes
  cleaned = cleaned.replace(/\/+$/, '');
  
  // Add https if missing
  if (!cleaned.startsWith('http://') && !cleaned.startsWith('https://')) {
    cleaned = 'https://' + cleaned;
  }
  
  // Prefer https
  if (cleaned.startsWith('http://')) {
    cleaned = cleaned.replace('http://', 'https://');
  }
  
  return cleaned;
}

/**
 * Extract store domain from URL for display
 */
export function getStoreDomain(url: string): string {
  try {
    const parsed = new URL(normalizeStoreUrl(url));
    return parsed.hostname;
  } catch {
    return url;
  }
}

// ============================================
// WOOCOMMERCE: Default & Transforms
// ============================================

export const DEFAULT_WOOCOMMERCE_FORM: WooCommerceConnectFormData = {
  store_url: '',
  store_name: '',
  consumer_key: '',
  consumer_secret: '',
};

export function formDataToWooCommerceRequest(form: WooCommerceConnectFormData): WooCommerceConnectRequest {
  return {
    store_url: normalizeStoreUrl(form.store_url),
    store_name: form.store_name.trim() || null,
    consumer_key: form.consumer_key.trim(),
    consumer_secret: form.consumer_secret.trim(),
  };
}

// ============================================
// SHOPIFY: Default & Transforms
// ============================================

export const DEFAULT_SHOPIFY_FORM: ShopifyConnectFormData = {
  store_url: '',
};

export function formDataToOAuthRequest(form: ShopifyConnectFormData, platform: EcommercePlatform): OAuthInitRequest {
  return {
    platform,
    store_url: normalizeStoreUrl(form.store_url),
  };
}

// ============================================
// INTEGRATION UPDATE: Default & Transforms
// ============================================

export const DEFAULT_INTEGRATION_UPDATE_FORM: IntegrationUpdateFormData = {
  store_name: '',
  is_paused: false,
};

export function integrationToUpdateFormData(integration: Partial<Integration>): IntegrationUpdateFormData {
  return {
    store_name: integration.store_name ?? '',
    is_paused: integration.status === 'paused',
  };
}

export function formDataToIntegrationUpdate(form: IntegrationUpdateFormData): IntegrationUpdate {
  return {
    store_name: form.store_name.trim() || null,
    status: form.is_paused ? 'paused' : 'active',
  };
}

// ============================================
// PRODUCT LINK: Default & Transforms
// ============================================

export const DEFAULT_PRODUCT_LINK_FORM: ProductLinkFormData = {
  product_id: '',
  external_product_id: '',
  external_variant_id: '',
};

export function formDataToProductLinkCreate(form: ProductLinkFormData): ProductLinkCreate {
  return {
    product_id: form.product_id,
    external_product_id: form.external_product_id.trim(),
    external_variant_id: form.external_variant_id.trim() || null,
  };
}

// ============================================
// VALIDATION
// ============================================

export function validateWooCommerceForm(form: WooCommerceConnectFormData): WooCommerceConnectFormErrors {
  const result = wooCommerceConnectSchema.safeParse(form);
  if (result.success) return {};

  const errors: WooCommerceConnectFormErrors = {};
  for (const issue of result.error.issues) {
    const path = issue.path[0] as keyof WooCommerceConnectFormData;
    if (path && !errors[path]) errors[path] = issue.message;
  }
  return errors;
}

export function validateShopifyForm(form: ShopifyConnectFormData): ShopifyConnectFormErrors {
  const result = shopifyConnectSchema.safeParse(form);
  if (result.success) return {};

  const errors: ShopifyConnectFormErrors = {};
  for (const issue of result.error.issues) {
    const path = issue.path[0] as keyof ShopifyConnectFormData;
    if (path && !errors[path]) errors[path] = issue.message;
  }
  return errors;
}

export function validateProductLinkForm(form: ProductLinkFormData): ProductLinkFormErrors {
  const result = productLinkSchema.safeParse(form);
  if (result.success) return {};

  const errors: ProductLinkFormErrors = {};
  for (const issue of result.error.issues) {
    const path = issue.path[0] as keyof ProductLinkFormData;
    if (path && !errors[path]) errors[path] = issue.message;
  }
  return errors;
}

/**
 * Validate and transform WooCommerce connection
 */
export function validateAndConnectWooCommerce(form: WooCommerceConnectFormData): 
  | { success: true; data: WooCommerceConnectRequest }
  | { success: false; errors: WooCommerceConnectFormErrors } {
  
  const errors = validateWooCommerceForm(form);
  if (Object.keys(errors).length > 0) return { success: false, errors };
  return { success: true, data: formDataToWooCommerceRequest(form) };
}

/**
 * Validate and transform Shopify OAuth init
 */
export function validateAndConnectShopify(form: ShopifyConnectFormData): 
  | { success: true; data: OAuthInitRequest }
  | { success: false; errors: ShopifyConnectFormErrors } {
  
  const errors = validateShopifyForm(form);
  if (Object.keys(errors).length > 0) return { success: false, errors };
  return { success: true, data: formDataToOAuthRequest(form, 'shopify') };
}

/**
 * Validate and transform product link creation
 */
export function validateAndCreateProductLink(form: ProductLinkFormData): 
  | { success: true; data: ProductLinkCreate }
  | { success: false; errors: ProductLinkFormErrors } {
  
  const errors = validateProductLinkForm(form);
  if (Object.keys(errors).length > 0) return { success: false, errors };
  return { success: true, data: formDataToProductLinkCreate(form) };
}

// ============================================
// DISPLAY HELPERS
// ============================================

/**
 * Get human-readable status label
 */
export function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: 'Active',
    error: 'Error',
    paused: 'Paused',
    disconnected: 'Disconnected',
  };
  return labels[status] ?? status;
}

/**
 * Get status color for badges
 */
export function getStatusColor(status: string): 'green' | 'red' | 'yellow' | 'gray' {
  const colors: Record<string, 'green' | 'red' | 'yellow' | 'gray'> = {
    active: 'green',
    error: 'red',
    paused: 'yellow',
    disconnected: 'gray',
  };
  return colors[status] ?? 'gray';
}

/**
 * Get sync status label
 */
export function getSyncStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    idle: 'Ready',
    syncing: 'Syncing...',
    error: 'Sync Failed',
  };
  return labels[status] ?? status;
}



