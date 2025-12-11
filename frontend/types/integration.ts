// frontend/types/integration.ts

/**
 * Integration Types
 * 
 * TypeScript definitions matching backend/schemas/integration.py
 */

// ==================== Enums ====================

export type EcommercePlatform = 'shopify' | 'woocommerce';

export type IntegrationStatus = 'active' | 'error' | 'paused' | 'disconnected';

export type SyncType = 'full' | 'incremental';

export type SyncStatus = 'idle' | 'syncing' | 'error';

export type HealthStatus = 'healthy' | 'unhealthy' | 'rate_limited' | 'unauthorized';

// ==================== OAuth ====================

export interface OAuthInitRequest {
  platform: EcommercePlatform;
  store_url: string;
}

export interface OAuthInitResponse {
  authorization_url: string;
  state: string;
}

// ==================== WooCommerce Connect ====================

export interface WooCommerceConnectRequest {
  store_url: string;
  store_name?: string;
  consumer_key: string;
  consumer_secret: string;
}

// ==================== Integration CRUD ====================

export interface Integration {
  id: string;
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

export interface IntegrationListResponse {
  integrations: Integration[];
  total: number;
}

export interface IntegrationUpdate {
  store_name?: string;
  status?: IntegrationStatus;
  settings?: Record<string, unknown>;
}

// ==================== Sync ====================

export interface SyncTriggerRequest {
  sync_type: SyncType;
}

export interface SyncStatusResponse {
  integration_id: string;
  sync_status: SyncStatus;
  last_sync_at: string | null;
  products_synced: number;
  current_progress?: number;
}

export interface SyncLog {
  id: string;
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

export interface SyncLogsResponse {
  items: SyncLog[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ==================== Product Links ====================

export interface ProductLinkCreate {
  product_id: string;
  external_product_id: string;
  external_variant_id?: string;
}

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

export interface ProductLinkListResponse {
  links: ProductLink[];
  total: number;
}

// ==================== Price Push ====================

export interface PricePushRequest {
  product_link_id: string;
  new_price: number;
  compare_at_price?: number;
}

export interface PricePushResponse {
  success: boolean;
  product_link_id: string;
  old_price: number | null;
  new_price: number;
  error: string | null;
}

export interface BulkPricePushRequest {
  updates: PricePushRequest[];
}

export interface BulkPricePushResponse {
  results: PricePushResponse[];
  success_count: number;
  failure_count: number;
}

// ==================== Health Check ====================

export interface IntegrationHealthResponse {
  integration_id: string;
  platform: EcommercePlatform;
  store_url: string;
  status: HealthStatus;
  checked_at: string;
}

// ==================== UI Helper Types ====================

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
