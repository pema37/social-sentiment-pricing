// API Client - handles all communication with the backend
import { getToken } from '@/lib/auth/token';
import type { ApiResponse } from '@/types';

// Backend URL - uses environment variable or defaults to localhost
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Options for API requests
interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;           // Data to send (will be converted to JSON)
  headers?: Record<string, string>;
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
      // Add Authorization header if we have a token
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
        error: errorData.detail || `Error: ${response.status}`,
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
  // Login - returns JWT token
  login: (email: string, password: string) =>
    apiClient<{ access_token: string; token_type: string }>('/api/v1/auth/login', {
      method: 'POST',
      body: { username: email, password }, // Backend expects "username" not "email"
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
  // Get all products for current user
  getAll: () => apiClient('/api/v1/products'),
  
  // Get a single product by ID
  getById: (id: string) => apiClient(`/api/v1/products/${id}`),
  
  // Create a new product
  create: (data: unknown) =>
    apiClient('/api/v1/products', { method: 'POST', body: data }),
  
  // Update an existing product
  update: (id: string, data: unknown) =>
    apiClient(`/api/v1/products/${id}`, { method: 'PATCH', body: data }),
  
  // Delete a product
  delete: (id: string) =>
    apiClient(`/api/v1/products/${id}`, { method: 'DELETE' }),
};

// ============================================
// Sentiment API - analyze and retrieve sentiment
// ============================================
export const sentimentApi = {
  // Analyze text content for sentiment
  analyze: (productId: string, content: string, source: string) =>
    apiClient('/api/v1/sentiment/analyze', {
      method: 'POST',
      body: { product_id: productId, content, source },
    }),
  
  // Get all sentiment data for a product
  getByProduct: (productId: string) =>
    apiClient(`/api/v1/sentiment/product/${productId}`),
};

// ============================================
// Pricing API - get and manage price suggestions
// ============================================
export const pricingApi = {
  // Get AI-generated price suggestion for a product
  getSuggestion: (productId: string) =>
    apiClient(`/api/v1/pricing/suggestion/${productId}`),
  
  // Accept a price suggestion
  acceptSuggestion: (suggestionId: string) =>
    apiClient(`/api/v1/pricing/suggestion/${suggestionId}/accept`, { method: 'POST' }),
  
  // Reject a price suggestion
  rejectSuggestion: (suggestionId: string) =>
    apiClient(`/api/v1/pricing/suggestion/${suggestionId}/reject`, { method: 'POST' }),
};
