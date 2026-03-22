// frontend/lib/api/client.ts

/**
 * API Client - handles fetch, auth, and errors
 * 
 * PATCHED (2025-01-07): Added automatic token refresh on 401 errors.
 * PATCHED (2025-01-15): Integrated centralized error parsing from errors.ts
 */

import {
  getBearerToken,
  setToken,
  setRefreshToken,
  removeAllTokens
} from '@/lib/auth/token';
import { ErrorCodes, type ErrorCode } from '@/lib/api/errors';

const getApiBaseUrl = () => {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl) {
    if (envUrl.includes('railway.app')) {
      return envUrl.replace('http://', 'https://');
    }
    return envUrl;
  }
  return 'http://localhost:8000';
};

// Custom error class for API errors - enhanced with error codes
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code: ErrorCode = ErrorCodes.UNKNOWN_ERROR,
    public details?: unknown,
    public fieldErrors?: Record<string, string[]>
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

// Request options
interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  headers?: Record<string, string>;
  params?: Record<string, string | number | boolean | undefined>;
  _isRetry?: boolean;
}

// Build query string from params
function buildQueryString(params?: Record<string, string | number | boolean | undefined>): string {
  if (!params) return '';
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      query.set(key, String(value));
    }
  });
  const queryString = query.toString();
  return queryString ? `?${queryString}` : '';
}

// Track if we're currently refreshing to prevent multiple refresh calls
let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

/**
 * Attempt to refresh the access token using the httpOnly refresh cookie.
 * The cookie is sent automatically via credentials: 'include'.
 */
async function refreshAccessToken(): Promise<boolean> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      return false;
    }

    const data = await response.json();

    // Backend sets new httpOnly cookies automatically.
    // Update the hint cookie so middleware stays in sync.
    if (data.access_token) {
      setToken(data.access_token);
    }
    if (data.refresh_token) {
      setRefreshToken(data.refresh_token);
    }

    return true;
  } catch {
    return false;
  }
}

/**
 * Handle token refresh with deduplication.
 */
async function handleTokenRefresh(): Promise<boolean> {
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }
  
  isRefreshing = true;
  refreshPromise = refreshAccessToken();
  
  try {
    const result = await refreshPromise;
    return result;
  } finally {
    isRefreshing = false;
    refreshPromise = null;
  }
}

// Handle final auth failure
function handleAuthError() {
  if (typeof window === 'undefined') return;
  
  removeAllTokens();
  
  const currentPath = window.location.pathname;
  if (currentPath !== '/login' && currentPath !== '/register') {
    sessionStorage.setItem('redirectAfterLogin', currentPath);
    window.location.href = '/login?expired=true';
  }
}

// Get error code from status
function getErrorCode(status: number): ErrorCode {
  switch (status) {
    case 400:
      return ErrorCodes.VALIDATION_ERROR;
    case 401:
      return ErrorCodes.AUTHENTICATION_ERROR;
    case 403:
      return ErrorCodes.AUTHORIZATION_ERROR;
    case 404:
      return ErrorCodes.NOT_FOUND;
    case 422:
      return ErrorCodes.VALIDATION_ERROR;
    case 429:
      return ErrorCodes.RATE_LIMIT;
    case 500:
    case 502:
    case 503:
    case 504:
      return ErrorCodes.SERVER_ERROR;
    default:
      return ErrorCodes.UNKNOWN_ERROR;
  }
}

// Parse validation errors into field-specific errors
function parseFieldErrors(errorData: unknown): Record<string, string[]> | undefined {
  if (!errorData || typeof errorData !== 'object') return undefined;
  
  const err = errorData as Record<string, unknown>;
  
  if (Array.isArray(err.detail)) {
    const fieldErrors: Record<string, string[]> = {};
    
    for (const item of err.detail) {
      if (item && typeof item === 'object' && 'loc' in item && 'msg' in item) {
        const loc = item.loc as (string | number)[];
        const field = loc[loc.length - 1]?.toString() || 'unknown';
        if (!fieldErrors[field]) {
          fieldErrors[field] = [];
        }
        fieldErrors[field].push(item.msg as string);
      }
    }
    
    return Object.keys(fieldErrors).length > 0 ? fieldErrors : undefined;
  }
  
  return undefined;
}

// Extract error message from API response
function parseErrorMessage(status: number, errorData: unknown): string {
  if (errorData && typeof errorData === 'object') {
    const err = errorData as Record<string, unknown>;
    
    // FastAPI validation errors
    if (Array.isArray(err.detail)) {
      const messages = err.detail
        .map((item: { msg?: string }) => item.msg || 'Validation error')
        .join(', ');
      return messages || 'Please check your input';
    }
    
    // Simple string error
    if (typeof err.detail === 'string') {
      const detail = err.detail;
      
      if (detail.toLowerCase().includes('already exists')) {
        return 'This email is already registered. Please sign in instead.';
      }
      if (detail.toLowerCase().includes('incorrect email or password')) {
        return 'Incorrect email or password. Please try again.';
      }
      if (detail.toLowerCase().includes('deactivated')) {
        return 'This account has been deactivated. Please contact support.';
      }
      if (detail.toLowerCase().includes('invalid') && detail.toLowerCase().includes('token')) {
        return 'Your session has expired. Please log in again.';
      }
      if (detail.toLowerCase().includes('expired')) {
        return 'Your session has expired. Please log in again.';
      }
      if (detail.toLowerCase().includes('could not validate credentials')) {
        return 'Your session has expired. Please log in again.';
      }
      
      return detail;
    }
    
    if (typeof err.message === 'string') {
      return err.message;
    }
  }
  
  switch (status) {
    case 400:
      return 'Invalid request. Please check your input.';
    case 401:
      return 'Your session has expired. Please log in again.';
    case 403:
      return 'Access denied.';
    case 404:
      return 'Resource not found.';
    case 409:
      return 'This email is already registered.';
    case 422:
      return 'Please check your input and try again.';
    case 429:
      return 'Too many attempts. Please wait a moment and try again.';
    case 500:
      return 'Server error. Please try again later.';
    case 502:
      return 'Server is starting up. Please try again in a moment.';
    case 503:
      return 'Service temporarily unavailable. Please try again later.';
    case 504:
      return 'Server timeout. Please try again.';
    default:
      return status > 0 
        ? `Request failed (error ${status}). Please try again.`
        : 'Unable to connect to server. Please check your connection.';
  }
}

// Main API client
export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = 'GET', body, headers = {}, params, _isRetry = false } = options;
  
  const queryString = buildQueryString(params);
  const url = `${getApiBaseUrl()}${endpoint}${queryString}`;

  // Shopify embedded flow: App Bridge session token sent as Bearer header.
  // Regular flow: httpOnly cookies sent automatically via credentials: 'include'.
  const bearer = getBearerToken();

  const config: RequestInit = {
    method,
    cache: 'no-store',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(bearer && { Authorization: `Bearer ${bearer}` }),
      ...headers,
    },
  };
  
  if (body) {
    config.body = JSON.stringify(body);
  }
  
  try {
    const response = await fetch(url, config);
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      
      // Handle 401 Unauthorized
      if (response.status === 401) {
        const isAuthEndpoint = endpoint.includes('/auth/login') || 
                               endpoint.includes('/auth/register') ||
                               endpoint.includes('/auth/refresh');
        
        if (_isRetry || isAuthEndpoint) {
          handleAuthError();
          throw new ApiError(
            response.status,
            parseErrorMessage(response.status, errorData),
            ErrorCodes.AUTHENTICATION_ERROR,
            errorData
          );
        }
        
        const refreshed = await handleTokenRefresh();
        
        if (refreshed) {
          return apiClient<T>(endpoint, { ...options, _isRetry: true });
        } else {
          handleAuthError();
        }
      }
      
      throw new ApiError(
        response.status,
        parseErrorMessage(response.status, errorData),
        getErrorCode(response.status),
        errorData,
        parseFieldErrors(errorData)
      );
    }
    
    if (response.status === 204) {
      return undefined as T;
    }
    
    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(
      0,
      error instanceof Error && error.message.includes('fetch')
        ? 'Unable to connect to server. Please check your internet connection.'
        : 'Network error. Please try again.',
      ErrorCodes.NETWORK_ERROR
    );
  }
}

// Convenience methods
export const api = {
  get: <T>(endpoint: string, params?: Record<string, string | number | boolean | undefined>) =>
    apiClient<T>(endpoint, { method: 'GET', params }),
  
  post: <T>(endpoint: string, body?: unknown) =>
    apiClient<T>(endpoint, { method: 'POST', body }),
  
  put: <T>(endpoint: string, body?: unknown) =>
    apiClient<T>(endpoint, { method: 'PUT', body }),
  
  patch: <T>(endpoint: string, body?: unknown) =>
    apiClient<T>(endpoint, { method: 'PATCH', body }),
  
  delete: <T>(endpoint: string) =>
    apiClient<T>(endpoint, { method: 'DELETE' }),
};


