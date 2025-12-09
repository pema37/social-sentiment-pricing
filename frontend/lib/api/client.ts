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
  isFormData?: boolean;
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
  const { method = 'GET', body, headers = {}, isFormData = false } = options;
  
  // Get JWT token if user is logged in
  const token = getToken();
  
  // Build the fetch configuration
  const config: RequestInit = {
    method,
    headers: {
      // Don't set Content-Type for FormData - browser sets it with boundary
      ...(!isFormData && { 'Content-Type': 'application/json' }),
      ...(token && { Authorization: `Bearer ${token}` }),
      ...headers,
    },
  };
  
  // Add body for POST/PUT/PATCH requests
  if (body) {
    config.body = isFormData ? (body as FormData) : JSON.stringify(body);
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
  // Login - returns JWT token (backend expects JSON with email/password)
  login: (email: string, password: string) =>
    apiClient<{ access_token: string; token_type: string }>('/api/v1/auth/login', {
      method: 'POST',
      body: { email, password },
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
  getAll: (params?: { skip?: number; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.skip) query.set('skip', params.skip.toString());
    if (params?.limit) query.set('limit', params.limit.toString());
    const queryString = query.toString();
    return apiClient(`/api/v1/products${queryString ? `?${queryString}` : ''}`);
  },
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
// Pricing API - get and manage price recommendations
// ============================================
export const pricingApi = {
  getRecommendations: (params?: { status?: string; product_id?: string }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.product_id) query.set('product_id', params.product_id);
    const queryString = query.toString();
    return apiClient(`/api/v1/pricing/recommendations${queryString ? `?${queryString}` : ''}`);
  },
  getRecommendation: (id: string) =>
    apiClient(`/api/v1/pricing/recommendations/${id}`),
  approveRecommendation: (id: string) =>
    apiClient(`/api/v1/pricing/recommendations/${id}/approve`, { method: 'POST' }),
  rejectRecommendation: (id: string) =>
    apiClient(`/api/v1/pricing/recommendations/${id}/reject`, { method: 'POST' }),
  applyRecommendation: (id: string) =>
    apiClient(`/api/v1/pricing/recommendations/${id}/apply`, { method: 'POST' }),
};

// ============================================
// Analytics API - dashboard stats and summaries
// ============================================

// Types matching backend schemas
export interface DashboardOverview {
  total_products: number;
  products_with_auto_pricing: number;
  total_competitors: number;
  unread_alerts: number;
  alerts_today: number;
  pending_recommendations: number;
  applied_recommendations_7d: number;
  average_sentiment: number | null;
  sentiment_trend: 'improving' | 'declining' | 'stable';
  total_mentions_24h: number;
}

export interface ProductSummary {
  id: string;
  name: string;
  sku: string | null;
  current_price: string;
  base_price: string;
  price_change_percent: number;
  sentiment_score: number | null;
  mention_count_24h: number;
  has_pending_recommendation: boolean;
  auto_pricing_enabled: boolean;
}

export interface RecommendationStats {
  total_pending: number;
  total_approved: number;
  total_rejected: number;
  total_applied: number;
  total_expired: number;
  avg_confidence_score: number | null;
  avg_adjustment_percent: number | null;
}

export interface AlertAnalytics {
  total_alerts: number;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
}

export interface SentimentDataPoint {
  timestamp: string;
  score: number;
  mention_count: number;
}

export interface SentimentTrend {
  product_id: string | null;
  period_days: number;
  current_score: number | null;
  previous_score: number | null;
  change: number | null;
  trend: 'up' | 'down' | 'stable';
  timeline: SentimentDataPoint[];
}

export const analyticsApi = {
  getDashboard: () => 
    apiClient<DashboardOverview>('/api/v1/analytics/dashboard'),
  
  getProductSummaries: (limit: number = 10) =>
    apiClient<ProductSummary[]>(`/api/v1/analytics/products?limit=${limit}`),
  
  getRecommendationStats: (days: number = 30) =>
    apiClient<RecommendationStats>(`/api/v1/analytics/recommendations/stats?days=${days}`),
  
  getAlertAnalytics: (days: number = 30) =>
    apiClient<AlertAnalytics>(`/api/v1/analytics/alerts/stats?days=${days}`),

  getSentimentTrend: (params?: { product_id?: string; days?: number; bucket?: string }) => {
    const query = new URLSearchParams();
    if (params?.product_id) query.set('product_id', params.product_id);
    if (params?.days) query.set('days', params.days.toString());
    if (params?.bucket) query.set('bucket', params.bucket);
    const queryString = query.toString();
    return apiClient<SentimentTrend>(`/api/v1/analytics/sentiment-trend${queryString ? `?${queryString}` : ''}`);
  },
};

// ============================================
// Alerts API - notifications and alerts
// ============================================

export interface Alert {
  id: string;
  alert_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  message: string;
  status: 'pending' | 'acknowledged' | 'resolved';
  product_id: string | null;
  recommendation_id: string | null;
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

export interface AlertStats {
  total_unread: number;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
  recent_24h: number;
}

export interface PaginatedAlerts {
  items: Alert[];
  total: number;
  skip: number;
  limit: number;
}

export const alertsApi = {
  getAll: (params?: { 
    skip?: number;
    limit?: number;
    status?: string; 
    severity?: string;
    alert_type?: string;
    product_id?: string;
  }) => {
    const query = new URLSearchParams();
    if (params?.skip) query.set('skip', params.skip.toString());
    if (params?.limit) query.set('limit', params.limit.toString());
    if (params?.status) query.set('status', params.status);
    if (params?.severity) query.set('severity', params.severity);
    if (params?.alert_type) query.set('alert_type', params.alert_type);
    if (params?.product_id) query.set('product_id', params.product_id);
    const queryString = query.toString();
    return apiClient<PaginatedAlerts>(`/api/v1/alerts${queryString ? `?${queryString}` : ''}`);
  },
  
  getStats: () => apiClient<AlertStats>('/api/v1/alerts/stats'),
  
  getUnreadCount: () => apiClient<{ unread_count: number }>('/api/v1/alerts/unread/count'),
  
  getById: (id: string) => apiClient<Alert>(`/api/v1/alerts/${id}`),
  
  acknowledge: (id: string) =>
    apiClient<Alert>(`/api/v1/alerts/${id}/acknowledge`, { method: 'POST' }),
  
  resolve: (id: string) =>
    apiClient<Alert>(`/api/v1/alerts/${id}/resolve`, { method: 'POST' }),
  
  acknowledgeAll: (params?: { severity?: string; alert_type?: string }) => {
    const query = new URLSearchParams();
    if (params?.severity) query.set('severity', params.severity);
    if (params?.alert_type) query.set('alert_type', params.alert_type);
    const queryString = query.toString();
    return apiClient<{ acknowledged_count: number }>(
      `/api/v1/alerts/acknowledge-all${queryString ? `?${queryString}` : ''}`,
      { method: 'POST' }
    );
  },
};

// ============================================
// Competitors API
// ============================================
export const competitorsApi = {
  getAll: (params?: { skip?: number; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.skip) query.set('skip', params.skip.toString());
    if (params?.limit) query.set('limit', params.limit.toString());
    const queryString = query.toString();
    return apiClient(`/api/v1/competitors${queryString ? `?${queryString}` : ''}`);
  },
  getById: (id: string) => apiClient(`/api/v1/competitors/${id}`),
  create: (data: unknown) =>
    apiClient('/api/v1/competitors', { method: 'POST', body: data }),
  update: (id: string, data: unknown) =>
    apiClient(`/api/v1/competitors/${id}`, { method: 'PATCH', body: data }),
  delete: (id: string) =>
    apiClient(`/api/v1/competitors/${id}`, { method: 'DELETE' }),
};
