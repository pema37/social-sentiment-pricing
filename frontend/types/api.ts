// Base API types
// AUTO-SYNCED with backend via openapi-typescript
// Last synced: 2026-01-08

/**
 * Generic API response wrapper
 * Used by the API client for consistent error handling
 */
export interface ApiResponse<T> {
  data: T | null;
  error: string | null;
  status: number;
}

/**
 * API error class thrown by the client
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Health check response
 * Matches: components["schemas"]["HealthResponse"]
 */
export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
}
