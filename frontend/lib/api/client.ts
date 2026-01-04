// API Client - handles fetch, auth, and errors
import { getToken } from '@/lib/auth/token';

const getApiBaseUrl = () => {
  // Use env var if set (works for both client and server)
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl) {
    if (envUrl.includes('railway.app')) {
      return envUrl.replace('http://', 'https://');
    }
    return envUrl;
  }
  
  // Fallback for local development
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

// Extract error message from API response
function parseErrorMessage(status: number, errorData: unknown): string {
  // Try to extract message from response body first
  if (errorData && typeof errorData === 'object') {
    const err = errorData as Record<string, unknown>;
    
    // FastAPI validation errors: { detail: [{ msg: "...", loc: [...] }] }
    if (Array.isArray(err.detail)) {
      const messages = err.detail
        .map((item: { msg?: string }) => item.msg || 'Validation error')
        .join(', ');
      return messages || 'Please check your input';
    }
    
    // Simple string error: { detail: "User already exists" }
    if (typeof err.detail === 'string') {
      const detail = err.detail;
      
      // Make certain backend messages more user-friendly
      if (detail.toLowerCase().includes('already exists')) {
        return 'This email is already registered. Please sign in instead.';
      }
      if (detail.toLowerCase().includes('incorrect email or password')) {
        return 'Incorrect email or password. Please try again.';
      }
      if (detail.toLowerCase().includes('deactivated')) {
        return 'This account has been deactivated. Please contact support.';
      }
      
      return detail;
    }
    
    // Generic message field
    if (typeof err.message === 'string') {
      return err.message;
    }
  }
  
  // Fallback based on status code
  switch (status) {
    case 400:
      return 'Invalid request. Please check your input.';
    case 401:
      return 'Invalid credentials. Please try again.';
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

// Main API client - throws on error, returns data on success
export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = 'GET', body, headers = {}, params } = options;
  
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
      throw new ApiError(
        response.status,
        parseErrorMessage(response.status, errorData),
        errorData
      );
    }
    
    // Handle 204 No Content
    if (response.status === 204) {
      return undefined as T;
    }
    
    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    // Network errors (no response from server)
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

