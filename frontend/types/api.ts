// Base API types

// Pagination wrapper for list endpoints
export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// Alternative pagination format (some endpoints use this)
export interface PaginatedWithSkip<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

// Generic API error response
export interface ApiErrorResponse {
  detail: string | Array<{ msg: string; loc: string[] }>;
}
