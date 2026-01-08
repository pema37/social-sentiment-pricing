// Common/shared types used across modules
// AUTO-SYNCED with backend via openapi-typescript
// Last synced: 2026-01-08

// ============================================
// PAGINATION
// ============================================

/**
 * Generic paginated response wrapper
 * Used by multiple endpoints
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// ============================================
// API ERROR TYPES
// ============================================

/**
 * HTTP validation error from FastAPI
 * Matches: components["schemas"]["HTTPValidationError"]
 */
export interface HTTPValidationError {
  detail: ValidationError[];
}

/**
 * Individual validation error
 * Matches: components["schemas"]["ValidationError"]
 */
export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/**
 * Generic API error response
 */
export interface ApiErrorResponse {
  detail?: string | ValidationError[];
  error?: string;
  message?: string;
  error_code?: string;
  suggestion?: string;
}

// Note: AlertChannel is defined in alert.ts
// Import it from there or from the main index.ts
