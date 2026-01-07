// frontend/lib/api/client.ts

/**
 * API Client - handles fetch, auth, and errors
 * 
 * PATCHED (2025-01-07): Added automatic token refresh on 401 errors.
 * - When a 401 is received, attempts to refresh the token
 * - If refresh succeeds, retries the original request
 * - If refresh fails, redirects to login
 */

import { 
  getToken, 
  setToken, 
  setRefreshToken,
  getRefreshToken, 
  removeAllTokens 
} from '@/lib/auth/token';

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

// Custom error class for API errors
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown
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
  _isRetry?: boolean; // Internal flag to prevent infinite retry loops
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
 * Attempt to refresh the access token using the refresh token.
 * Returns true if successful, false otherwise.
 */
async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  
  if (!refreshToken) {
    return false;
  }
  
  try {
    const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    
    if (!response.ok) {
      return false;
    }
    
    const data = await response.json();
    
    // Save new tokens
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
 * Multiple concurrent 401s will share the same refresh request.
 */
async function handleTokenRefresh(): Promise<boolean> {
  // If already refreshing, wait for that to complete
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

// Handle final auth failure - clear tokens and redirect to login
function handleAuthError() {
  if (typeof window === 'undefined') return;
  
  removeAllTokens();
  
  const currentPath = window.location.pathname;
  if (currentPath !== '/login' && currentPath !== '/register') {
    sessionStorage.setItem('redirectAfterLogin', currentPath);
    window.location.href = '/login?expired=true';
  }
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
    default:
      return 'An error occurred. Please try again.';
  }
}

// Main API client
export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = 'GET', body, headers = {}, params, _isRetry = false } = options;
  
  const token = getToken();
  const queryString = buildQueryString(params);
  const url = `${getApiBaseUrl()}${endpoint}${queryString}`;
  
  const config: RequestInit = {
    method,
    cache: 'no-store',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
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
        // Don't try to refresh for auth endpoints themselves
        const isAuthEndpoint = endpoint.includes('/auth/login') || 
                               endpoint.includes('/auth/register') ||
                               endpoint.includes('/auth/refresh');
        
        // If this is already a retry, or it's an auth endpoint, give up
        if (_isRetry || isAuthEndpoint) {
          handleAuthError();
          throw new ApiError(
            response.status,
            parseErrorMessage(response.status, errorData),
            errorData
          );
        }
        
        // Try to refresh the token
        const refreshed = await handleTokenRefresh();
        
        if (refreshed) {
          // Retry the original request with the new token
          return apiClient<T>(endpoint, { ...options, _isRetry: true });
        } else {
          // Refresh failed, redirect to login
          handleAuthError();
        }
      }
      
      throw new ApiError(
        response.status,
        parseErrorMessage(response.status, errorData),
        errorData
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
        : 'Network error. Please try again.'
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



