// Product domain types
// AUTO-SYNCED with backend via openapi-typescript
// Last synced: 2026-01-08
// Source: components["schemas"]["ProductCreate"], ProductRead, ProductUpdate

// ============================================
// PRODUCT TYPES - Matches backend exactly
// ============================================

/**
 * Product response from GET endpoints
 * Matches: components["schemas"]["ProductRead"]
 */
export interface Product {
  id: string;
  user_id: string;
  name: string;
  sku: string | null;
  description: string | null;
  category: string | null;
  image_url: string | null;
  is_active: boolean;
  base_price: string;        // Decimal returned as string
  current_price: string;     // Decimal returned as string
  cost: string | null;       // Decimal returned as string
  min_price: string | null;  // Decimal returned as string
  max_price: string | null;  // Decimal returned as string
  sentiment_multiplier: string; // Decimal returned as string
  auto_pricing_enabled: boolean;
  keywords: string[];
  created_at: string;        // ISO 8601 datetime
  updated_at: string;        // ISO 8601 datetime
}

/**
 * Create product request
 * Matches: components["schemas"]["ProductCreate"]
 * 
 * Note: Decimal fields accept number | string for flexibility
 * Backend Pydantic will coerce to Decimal
 */
export interface CreateProductRequest {
  name: string;
  sku?: string | null;
  description?: string | null;
  base_price: number | string;  // Required - accepts both
  category?: string | null;
  image_url?: string | null;
  is_active?: boolean;          // Default: true
  cost?: number | string | null;
  min_price?: number | string | null;
  max_price?: number | string | null;
  sentiment_multiplier?: number | string; // Default: 0.1
  auto_pricing_enabled?: boolean;         // Default: false
  keywords?: string[];                    // Default: []
}

/**
 * Update product request
 * Matches: components["schemas"]["ProductUpdate"]
 * All fields optional for PATCH semantics
 */
export interface UpdateProductRequest {
  name?: string | null;
  sku?: string | null;
  description?: string | null;
  base_price?: number | string | null;
  current_price?: number | string | null;
  category?: string | null;
  image_url?: string | null;
  is_active?: boolean | null;
  cost?: number | string | null;
  min_price?: number | string | null;
  max_price?: number | string | null;
  sentiment_multiplier?: number | string | null;
  auto_pricing_enabled?: boolean | null;
  keywords?: string[] | null;
}

// ============================================
// PAGINATED RESPONSE
// ============================================

/**
 * Paginated products response
 * Matches: components["schemas"]["PaginatedResponse_ProductRead_"]
 */
export interface PaginatedProducts {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  total_pages?: number;  // Alias for pages
}

// ============================================
// PRICE SUGGESTION (AI-generated)
// ============================================

/**
 * Price suggestion from AI endpoint
 * Note: This is returned from /products/{id}/suggestion
 */
export interface PriceSuggestion {
  product_id: string;
  current_price: number;
  suggested_price: number;
  change_percent: number;
  reasoning: string;
  confidence: number;
  factors: {
    sentiment_score: number | null;
    competitor_avg_price?: number | null;
    mention_count?: number;
    mention_volume?: number;
    trend?: string;
    ai_key_factors?: string[];
    ai_powered?: boolean;
  };
}

// ============================================
// PRICE HISTORY
// ============================================

/**
 * Price history entry
 * Matches: components["schemas"]["PriceHistoryResponse"]
 */
export interface PriceHistoryEntry {
  id: string;
  product_id: string;
  price: string;
  source: string;
  change_reason: string | null;
  created_at: string;
}

// ============================================
// PRODUCT SUMMARY (Dashboard)
// ============================================

/**
 * Product summary for dashboard cards
 * Matches: components["schemas"]["ProductSummary"]
 */
export interface ProductSummary {
  id: string;
  name: string;
  sku?: string | null;
  current_price: string;
  base_price: string;
  price_change_percent: number;
  sentiment_score?: number | null;
  mention_count_24h: number;        // Default: 0
  has_pending_recommendation: boolean; // Default: false
  auto_pricing_enabled: boolean;    // Default: false
}
