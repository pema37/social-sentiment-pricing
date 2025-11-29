// Standard API response wrapper - every API call returns this shape
export interface ApiResponse<T> {
  data: T | null;         // The actual data (or null if error)
  error: string | null;   // Error message (or null if success)
  status: number;         // HTTP status code (200, 401, 500, etc.)
}

// For endpoints that return lists with pagination
export interface PaginatedResponse<T> {
  items: T[];             // Array of items (products, sentiments, etc.)
  total: number;          // Total number of items in database
  page: number;           // Current page number
  page_size: number;      // Items per page
  total_pages: number;    // Total number of pages
}

// Standard error format from the backend
export interface ApiError {
  detail: string;         // Error message
  status_code: number;    // HTTP status code
}

// Price suggestion from the pricing engine
export interface PriceSuggestion {
  id: string;                   // Unique identifier
  product_id: string;           // Which product this is for
  current_price: number;        // Current price of the product
  suggested_price: number;      // AI-suggested new price
  change_percentage: number;    // Percentage change (e.g., +3.5 or -2.1)
  reason: string;               // Why this price is suggested
  sentiment_score: number;      // Sentiment score that influenced this
  status: 'pending' | 'accepted' | 'rejected'; // User decision
  created_at: string;           // When suggestion was created
}
