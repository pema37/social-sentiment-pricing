// Competitor domain types
// AUTO-SYNCED with backend via openapi-typescript
// Last synced: 2026-01-08
// Source: components["schemas"]["CompetitorCreate"], CompetitorResponse, etc.

// ============================================
// COMPETITOR TYPES
// ============================================

/**
 * Competitor response from GET endpoints
 * Matches: components["schemas"]["CompetitorResponse"]
 */
export interface Competitor {
  id: string;
  user_id: string;
  name: string;
  website: string | null;
  description: string | null;
  scraping_config: Record<string, unknown> | null;
  is_active: boolean;
  scrape_frequency_minutes: number;  // Default: 60
  last_scraped_at: string | null;
  consecutive_failures: number;      // Default: 0
  created_at: string;
  updated_at: string;
}

/**
 * Paginated competitors response
 */
export interface PaginatedCompetitors {
  items: Competitor[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/**
 * Create competitor request
 * Matches: components["schemas"]["CompetitorCreate"]
 */
export interface CreateCompetitorRequest {
  name: string;
  website?: string | null;
  description?: string | null;
  scraping_config?: Record<string, unknown>;
  is_active?: boolean;                    // Default: true
  scrape_frequency_minutes?: number;      // Default: 60
}

/**
 * Update competitor request
 * Matches: components["schemas"]["CompetitorUpdate"]
 */
export interface UpdateCompetitorRequest {
  name?: string | null;
  website?: string | null;
  description?: string | null;
  scraping_config?: Record<string, unknown> | null;
  is_active?: boolean | null;
  scrape_frequency_minutes?: number | null;
}

// ============================================
// COMPETITOR PRODUCT TYPES
// ============================================

/**
 * Competitor product (price tracking)
 * Matches: components["schemas"]["CompetitorProductResponse"]
 */
export interface CompetitorProduct {
  id: string;
  product_id: string;
  competitor_id: string;
  competitor_product_name: string;
  competitor_product_url?: string;
  competitor_sku: string | null;
  currency: string;                    // Default: "USD"
  match_confidence: string;            // Decimal as string, Default: "1.0"
  notes: string | null;
  is_active: boolean;                  // Default: true
  current_price: string | null;
  last_price_update: string | null;
  price_available: boolean;            // Default: true
  created_at: string;
  updated_at: string;
}

/**
 * Paginated competitor products
 */
export interface PaginatedCompetitorProducts {
  items: CompetitorProduct[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/**
 * Competitor product with details (extended response)
 * Matches: components["schemas"]["CompetitorProductWithDetails"]
 */
export interface CompetitorProductWithDetails extends CompetitorProduct {
  competitor_name: string;
  your_product_name: string;
  your_current_price: string;
  price_difference: string | null;
  price_difference_percent: string | null;
}

/**
 * Create competitor product request
 * Matches: components["schemas"]["CompetitorProductCreate"]
 */
export interface CreateCompetitorProductRequest {
  product_id: string;
  competitor_id: string;
  competitor_product_name: string;
  competitor_product_url?: string;
  competitor_sku?: string | null;
  currency?: string;                         // Default: "USD"
  match_confidence?: number | string;        // Default: 1.0
  notes?: string | null;
  is_active?: boolean;                       // Default: true
  current_price?: number | string | null;    // Decimal field
}

/**
 * Update competitor product request
 * Matches: components["schemas"]["CompetitorProductUpdate"]
 */
export interface UpdateCompetitorProductRequest {
  competitor_product_name?: string | null;
  competitor_product_url?: string | null;
  competitor_sku?: string | null;
  currency?: string | null;
  match_confidence?: number | string | null;
  notes?: string | null;
  is_active?: boolean | null;
  current_price?: number | string | null;
}

// ============================================
// COMPETITOR PRICE HISTORY
// ============================================

/**
 * Competitor price history entry
 * Matches: components["schemas"]["CompetitorPriceHistoryResponse"]
 */
export interface CompetitorPriceHistory {
  id: string;
  competitor_product_id: string;
  old_price: string | null;
  new_price: string;
  currency: string;
  change_amount: string | null;
  change_percent: string | null;
  change_type: string;
  detected_promotion: boolean;
  promotion_name: string | null;
  was_available: boolean;
  is_available: boolean;
  observed_at: string;
}

/**
 * Paginated price history
 * Matches: components["schemas"]["CompetitorPriceHistoryListResponse"]
 */
export interface CompetitorPriceHistoryListResponse {
  items: CompetitorPriceHistory[];
  total: number;
}

// ============================================
// PRICE COMPARISON
// ============================================

/**
 * Price comparison response
 * Matches: components["schemas"]["CompetitorPriceComparison"]
 */
export interface CompetitorPriceComparison {
  product_id: string;
  product_name: string;
  your_price: string;
  competitor_prices: Record<string, unknown>[];
  lowest_competitor_price: string | null;
  highest_competitor_price: string | null;
  average_competitor_price: string | null;
  your_position: string;
  recommendation: string;
}

// ============================================
// COMPETITOR ALERT
// ============================================

/**
 * Alert for significant competitor price changes
 * Matches: components["schemas"]["CompetitorAlert"]
 */
export interface CompetitorAlert {
  alert_type: string;
  competitor_name: string;
  competitor_product_name: string;
  product_id: string;
  your_product_name: string;
  old_price: string | null;
  new_price: string;
  change_percent: string | null;
  your_current_price: string;
  suggested_action: string;
  observed_at: string;
}


