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
  skip: number;
  limit: number;
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
  current_price: string | null;
  last_scraped_at: string | null;
  created_at: string;
  updated_at: string;
}

// Competitor price history
export interface CompetitorPriceHistory {
  id: string;
  competitor_product_id: string;
  price: string;
  scraped_at: string;
}
