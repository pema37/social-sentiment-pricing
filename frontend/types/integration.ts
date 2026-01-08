// Integration Types
// AUTO-SYNCED with backend via openapi-typescript
// Last synced: 2026-01-08
// Source: components["schemas"]["IntegrationResponse"], etc.

// ============================================
// ENUMS / UNION TYPES
// ============================================

export type EcommercePlatform = 'shopify' | 'woocommerce';

export type IntegrationStatus = 'active' | 'error' | 'paused' | 'disconnected';

export type SyncType = 'full' | 'incremental';

export type SyncStatus = 'idle' | 'syncing' | 'error';

export type HealthStatus = 'healthy' | 'unhealthy' | 'rate_limited' | 'unauthorized';

// ============================================
// OAUTH TYPES
// ============================================

/**
 * OAuth init request
 * Matches: components["schemas"]["OAuthInitRequest"]
 */
export interface OAuthInitRequest {
  platform: EcommercePlatform;
  store_url: string;
}

/**
 * OAuth init response
 * Matches: components["schemas"]["OAuthInitResponse"]
 */
export interface OAuthInitResponse {
  authorization_url: string;
  state: string;
}

// ============================================
// WOOCOMMERCE CONNECT
// ============================================

/**
 * WooCommerce connect request
 * Matches: components["schemas"]["WooCommerceConnectRequest"]
 */
export interface WooCommerceConnectRequest {
  store_url: string;
  store_name?: string | null;
  consumer_key: string;
  consumer_secret: string;
}

// ============================================
// INTEGRATION CRUD
// ============================================

/**
 * Integration response from GET endpoints
 * Matches: components["schemas"]["IntegrationResponse"]
 */
export interface Integration {
  id: string;
  user_id: string;
  platform: EcommercePlatform;
  store_url: string;
  store_name: string | null;
  status: IntegrationStatus;
  error_message: string | null;
  scopes: string[];
  last_sync_at: string | null;
  sync_status: SyncStatus;
  products_synced: number;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/**
 * Integration list response
 * Matches: components["schemas"]["IntegrationListResponse"]
 */
export interface IntegrationListResponse {
  integrations: Integration[];
  total: number;
}

/**
 * Integration update request
 * Matches: components["schemas"]["IntegrationUpdate"]
 */
export interface IntegrationUpdate {
  store_name?: string | null;
  status?: IntegrationStatus | null;
  settings?: Record<string, unknown> | null;
}

// ============================================
// SYNC TYPES
// ============================================

/**
 * Sync trigger request
 * Matches: components["schemas"]["SyncTriggerRequest"]
 */
export interface SyncTriggerRequest {
  sync_type?: SyncType;  // Default: "incremental"
}

/**
 * Sync status response
 * Matches: components["schemas"]["SyncStatusResponse"]
 */
export interface SyncStatusResponse {
  integration_id: string;
  sync_status: SyncStatus;
  last_sync_at: string | null;
  products_synced: number;
  current_progress?: number | null;
}

/**
 * Sync log entry
 * Matches: components["schemas"]["SyncLogResponse"]
 */
export interface SyncLog {
  id: string;
  integration_id: string;
  sync_type: SyncType;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  success: boolean;
  products_created: number;
  products_updated: number;
  products_deleted: number;
  error_details: string | null;
}

/**
 * Sync logs list response
 */
export interface SyncLogsResponse {
  items: SyncLog[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ============================================
// PRODUCT LINK TYPES
// ============================================

/**
 * Create product link request
 * Matches: components["schemas"]["ProductLinkCreate"]
 */
export interface ProductLinkCreate {
  product_id: string;
  external_product_id: string;
  external_variant_id?: string | null;
}

/**
 * Product link response
 * Matches: components["schemas"]["ProductLinkResponse"]
 */
export interface ProductLink {
  id: string;
  product_id: string;
  integration_id: string;
  external_product_id: string;
  external_variant_id: string | null;
  external_price: number | null;
  external_compare_at_price: number | null;
  last_price_push_at: string | null;
  last_price_pull_at: string | null;
  sync_enabled: boolean;
  created_at: string;
}

/**
 * Product link list response
 * Matches: components["schemas"]["ProductLinkListResponse"]
 */
export interface ProductLinkListResponse {
  links: ProductLink[];
  total: number;
}

// ============================================
// PRICE PUSH TYPES
// ============================================

/**
 * Price push request
 * Matches: components["schemas"]["PricePushRequest"]
 */
export interface PricePushRequest {
  product_link_id: string;
  new_price: number | string;
  compare_at_price?: number | string | null;
}

/**
 * Price push response
 * Matches: components["schemas"]["PricePushResponse"]
 */
export interface PricePushResponse {
  success: boolean;
  product_link_id: string;
  old_price: number | null;
  new_price: number;
  error: string | null;
}

/**
 * Bulk price push request
 * Matches: components["schemas"]["BulkPricePushRequest"]
 */
export interface BulkPricePushRequest {
  updates: PricePushRequest[];
}

/**
 * Bulk price push response
 * Matches: components["schemas"]["BulkPricePushResponse"]
 */
export interface BulkPricePushResponse {
  results: PricePushResponse[];
  success_count: number;
  failure_count: number;
}

// ============================================
// HEALTH CHECK TYPES
// ============================================

/**
 * Integration health response
 * Matches: components["schemas"]["IntegrationHealthResponse"]
 */
export interface IntegrationHealthResponse {
  integration_id: string;
  platform: EcommercePlatform;
  store_url: string;
  status: HealthStatus;
  checked_at: string;
}

// ============================================
// UI HELPER TYPES (Frontend-only)
// ============================================

export interface PlatformConfig {
  id: EcommercePlatform;
  name: string;
  logo: string;
  description: string;
  authType: 'oauth' | 'api_key';
  docsUrl: string;
}

export const PLATFORM_CONFIGS: Record<EcommercePlatform, PlatformConfig> = {
  shopify: {
    id: 'shopify',
    name: 'Shopify',
    logo: '/logos/shopify.svg',
    description: 'Connect your Shopify store via OAuth',
    authType: 'oauth',
    docsUrl: 'https://shopify.dev/docs/apps/auth/oauth',
  },
  woocommerce: {
    id: 'woocommerce',
    name: 'WooCommerce',
    logo: '/logos/woocommerce.svg',
    description: 'Connect with REST API keys',
    authType: 'api_key',
    docsUrl: 'https://woocommerce.com/document/woocommerce-rest-api/',
  },
};
