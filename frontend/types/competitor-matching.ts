// frontend/types/competitor-matching.ts

/**
 * Types for Competitor Matching feature
 * Auto URL matching via Google Shopping, Custom Search, DuckDuckGo
 */

// ============================================
// SEARCH PROVIDERS
// ============================================

export type SearchProvider =
  | 'serpapi_google_shopping'
  | 'google_custom_search'
  | 'duckduckgo'
  | 'keepa'
  | 'rainforest';

export type MatchStatus = 'success' | 'partial' | 'failed' | 'cached';

// ============================================
// MATCHED PRODUCT
// ============================================

/**
 * A competitor product found via search
 */
export interface MatchedProduct {
  title: string;
  url: string;
  price: string | null;
  currency: string;
  merchant: string;
  merchant_domain: string;
  image_url: string | null;
  rating: number | null;
  reviews_count: number | null;
  confidence_score: number;
  confidence_percent: number;
  source: SearchProvider;
  in_stock: boolean;
}

// ============================================
// REQUEST TYPES
// ============================================

/**
 * Request to search for competitor products
 */
export interface CompetitorSearchRequest {
  product_name: string;
  keywords?: string[];
  our_price?: string | number;
  max_results?: number;
  exclude_domains?: string[];
  preferred_merchants?: string[];
  min_confidence?: number;
  use_cache?: boolean;
}

/**
 * Request to find competitors for a specific product
 */
export interface ProductMatchRequest {
  product_id: string;
  max_results?: number;
  exclude_domains?: string[];
  preferred_merchants?: string[];
  auto_link?: boolean;
  auto_link_threshold?: number;
}

/**
 * Request for bulk matching
 */
export interface BulkMatchRequest {
  product_ids: string[];
  max_results_per_product?: number;
  auto_link?: boolean;
  auto_link_threshold?: number;
}

// ============================================
// RESPONSE TYPES
// ============================================

/**
 * Response from competitor search
 */
export interface CompetitorSearchResponse {
  success: boolean;
  status: MatchStatus;
  query_used: string;
  total_found: number;
  products: MatchedProduct[];
  providers_used: SearchProvider[];
  providers_failed: string[];
  search_time_ms: number;
  cached: boolean;
}

/**
 * Information about a search provider
 */
export interface ProviderInfo {
  name: SearchProvider;
  available: boolean;
  requires_api_key: boolean;
  cost_per_request: number;
}

/**
 * Response listing available providers
 */
export interface ProvidersListResponse {
  providers: ProviderInfo[];
  available_count: number;
  total_count: number;
}

/**
 * Result for a single product in bulk match
 */
export interface BulkMatchResult {
  product_name: string;
  success: boolean;
  total_found?: number;
  error?: string;
  top_matches?: {
    title: string;
    merchant: string;
    price: string | null;
    url: string;
    confidence: number;
  }[];
}

/**
 * Response from bulk match operation
 */
export interface BulkMatchResponse {
  total_products: number;
  results: Record<string, BulkMatchResult>;
}

/**
 * Response from cache clear
 */
export interface CacheClearResponse {
  success: boolean;
  entries_cleared: number;
}


