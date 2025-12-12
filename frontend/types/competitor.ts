// Competitor domain types

// Competitor from the API
export interface Competitor {
  id: string;
  user_id: string;
  name: string;
  website: string | null;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Paginated competitors
export interface PaginatedCompetitors {
  items: Competitor[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Create competitor request
export interface CreateCompetitorRequest {
  name: string;
  website?: string;
  description?: string;
}

// Update competitor request
export interface UpdateCompetitorRequest {
  name?: string;
  website?: string;
  description?: string;
  is_active?: boolean;
}

// Competitor product (price tracking)
export interface CompetitorProduct {
  id: string;
  competitor_id: string;
  product_id: string;
  competitor_product_name: string;
  competitor_product_url: string | null;
  competitor_sku: string | null;
  current_price: string | null;
  currency: string;
  match_confidence: number | null;
  notes: string | null;
  is_active: boolean;
  price_available: boolean;
  last_price_update: string | null;
  last_scraped_at: string | null;
  created_at: string;
  updated_at: string;
}

// Paginated competitor products
export interface PaginatedCompetitorProducts {
  items: CompetitorProduct[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Competitor product with details
export interface CompetitorProductWithDetails extends CompetitorProduct {
  competitor_name: string;
  your_product_name: string;
  your_current_price: string | null;
  price_difference: string | null;
  price_difference_percent: string | null;
}

// Create competitor product request
export interface CreateCompetitorProductRequest {
  competitor_id: string;
  product_id: string;
  competitor_product_name: string;
  competitor_product_url?: string;
  competitor_sku?: string;
  current_price?: string;
  currency?: string;
  match_confidence?: number;
  notes?: string;
  is_active?: boolean;
}

// Update competitor product request
export interface UpdateCompetitorProductRequest {
  competitor_product_name?: string;
  competitor_product_url?: string;
  competitor_sku?: string;
  current_price?: string;
  currency?: string;
  match_confidence?: number;
  notes?: string;
  is_active?: boolean;
}

// Competitor price history
export interface CompetitorPriceHistory {
  id: string;
  competitor_product_id: string;
  old_price: string | null;
  new_price: string;
  currency: string;
  change_amount: string;
  change_percent: string;
  change_type: string;
  detected_promotion: boolean;
  was_available: boolean;
  is_available: boolean;
  observed_at: string;
}

// Price comparison response
export interface CompetitorPriceComparison {
  product_id: string;
  product_name: string;
  your_price: string;
  competitor_prices: {
    competitor_name: string;
    price: string;
    url: string | null;
    difference: string;
    difference_percent: string | null;
    last_updated: string | null;
  }[];
  lowest_competitor_price: string | null;
  highest_competitor_price: string | null;
  average_competitor_price: string | null;
  your_position: 'lowest' | 'highest' | 'middle' | 'no_data';
  recommendation: string;
}
