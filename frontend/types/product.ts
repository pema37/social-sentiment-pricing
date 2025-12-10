// Product domain types

export type ProductType = 'physical' | 'digital' | 'subscription' | 'service';

// Product from the API
export interface Product {
  id: string;
  user_id: string;
  name: string;
  sku: string | null;
  description: string | null;
  base_price: string;
  current_price: string;
  currency: string;
  product_type: ProductType;
  category: string | null;
  image_url: string | null;
  external_id: string | null;
  platform: string | null;
  platform_url: string | null;
  auto_pricing_enabled: boolean;
  min_price: string | null;
  max_price: string | null;
  sentiment_multiplier: string;
  is_active: boolean;
  keywords: string[];
  created_at: string;
  updated_at: string;
}

// Paginated products response
export interface PaginatedProducts {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  total_pages: number; // Alias for pages
}

// Create product request
export interface CreateProductRequest {
  name: string;
  sku?: string;
  description?: string;
  base_price: number;
  current_price?: number;
  currency?: string;
  product_type?: ProductType;
  category?: string;
  image_url?: string;
  auto_pricing_enabled?: boolean;
  min_price?: number;
  max_price?: number;
  sentiment_multiplier?: number;
  keywords?: string[];
}

// Update product request
export interface UpdateProductRequest {
  name?: string;
  sku?: string;
  description?: string;
  base_price?: number;
  current_price?: number;
  currency?: string;
  product_type?: ProductType;
  category?: string;
  image_url?: string;
  auto_pricing_enabled?: boolean;
  min_price?: number;
  max_price?: number;
  sentiment_multiplier?: number;
  is_active?: boolean;
  keywords?: string[];
}

// Price suggestion from AI
export interface PriceSuggestion {
  suggested_price: number;
  confidence: number;
  reasoning: string;
  price_change_percent: number;
  sentiment_score: number | null;
  mention_volume: number;
  factors: {
    sentiment_score: number | null;
    competitor_avg_price: number | null;
    mention_count: number;
  };
}

// Price history entry
export interface PriceHistoryEntry {
  id: string;
  product_id: string;
  price: string;
  source: string;
  change_reason: string | null;
  created_at: string;
}

// Product summary for dashboard
export interface ProductSummary {
  id: string;
  name: string;
  sku: string | null;
  current_price: string;
  base_price: string;
  price_change_percent: number;
  sentiment_score: number | null;
  mention_count_24h: number;
  has_pending_recommendation: boolean;
  auto_pricing_enabled: boolean;
}
