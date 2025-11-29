// API Client - handles all communication with the backend
import { getToken } from '@/lib/auth/token';
import type { ApiResponse } from '@/types';

// Backend URL - uses environment variable or defaults to localhost
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Options for API requests
interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  headers?: Record<string, string>;
}

// Helper to extract error message from API response
function getErrorMessage(errorData: unknown): string {
  if (!errorData || typeof errorData !== 'object') {
    return 'An error occurred';
  }
  
  const err = errorData as Record<string, unknown>;
  
  // FastAPI validation errors: { detail: [{ msg: "...", loc: [...] }] }
  if (Array.isArray(err.detail)) {
    return err.detail
      .map((item: { msg?: string }) => item.msg || 'Validation error')
      .join(', ');
  }
  
  // Simple string error: { detail: "Incorrect email or password" }
  if (typeof err.detail === 'string') {
    return err.detail;
  }
  
  return 'An error occurred';
}

// Main API client function - wraps fetch with auth and error handling
export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<ApiResponse<T>> {
  const { method = 'GET', body, headers = {} } = options;
  
  // Get JWT token if user is logged in
  const token = getToken();
  
  // Build the fetch configuration
  const config: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...headers,
    },
  };
  
  // Add body for POST/PUT/PATCH requests
  if (body) {
    config.body = JSON.stringify(body);
  }
  
  try {
    // Make the request
    const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
    
    // Handle error responses
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        data: null,
        error: getErrorMessage(errorData),
        status: response.status,
      };
    }
    
    // Parse and return successful response
    const data = await response.json();
    return {
      data,
      error: null,
      status: response.status,
    };
  } catch (error) {
    // Handle network errors
    return {
      data: null,
      error: error instanceof Error ? error.message : 'Network error',
      status: 0,
    };
  }
}

// ============================================
// Auth API - login, register, get current user
// ============================================
export const authApi = {
  // Login - returns JWT token (JSON body with email/password)
  login: (email: string, password: string) =>
    apiClient<{ access_token: string; token_type: string }>('/api/v1/auth/login', {
      method: 'POST',
      body: { email, password },  // Backend expects { email, password }
    }),
  
  // Register - creates new user account
  register: (email: string, password: string, fullName: string) =>
    apiClient<{ id: string; email: string }>('/api/v1/auth/register', {
      method: 'POST',
      body: { email, password, full_name: fullName },
    }),
  
  // Get current logged-in user
  me: () => apiClient('/api/v1/auth/me'),
};

// ============================================
// Products API - CRUD operations for products
// ============================================
export const productsApi = {
  getAll: () => apiClient('/api/v1/products'),
  getById: (id: string) => apiClient(`/api/v1/products/${id}`),
  create: (data: unknown) =>
    apiClient('/api/v1/products', { method: 'POST', body: data }),
  update: (id: string, data: unknown) =>
    apiClient(`/api/v1/products/${id}`, { method: 'PATCH', body: data }),
  delete: (id: string) =>
    apiClient(`/api/v1/products/${id}`, { method: 'DELETE' }),
};

// ============================================
// Sentiment API - analyze and retrieve sentiment
// ============================================
export const sentimentApi = {
  analyze: (productId: string, content: string, source: string) =>
    apiClient('/api/v1/sentiment/analyze', {
      method: 'POST',
      body: { product_id: productId, content, source },
    }),
  getByProduct: (productId: string) =>
    apiClient(`/api/v1/sentiment/product/${productId}`),
};

// ============================================
// Pricing API - get and manage price suggestions
// ============================================
export const pricingApi = {
  getSuggestion: (productId: string) =>
    apiClient(`/api/v1/pricing/suggestion/${productId}`),
  acceptSuggestion: (suggestionId: string) =>
    apiClient(`/api/v1/pricing/suggestion/${suggestionId}/accept`, { method: 'POST' }),
  rejectSuggestion: (suggestionId: string) =>
    apiClient(`/api/v1/pricing/suggestion/${suggestionId}/reject`, { method: 'POST' }),
};

