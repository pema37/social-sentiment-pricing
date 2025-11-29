const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ApiResponse<T> {
  data?: T;
  error?: string;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return { error: errorData.detail || `Error: ${response.status}` };
    }

    const data = await response.json();
    return { data };
  } catch (error) {
    return { error: 'Network error. Please try again.' };
  }
}

// Auth API calls
export const authApi = {
  login: (email: string, password: string) =>
    apiClient<{ access_token: string; token_type: string }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  register: (email: string, password: string, full_name?: string) =>
    apiClient<{ id: string; email: string }>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name }),
    }),
};

// Products API calls
export const productsApi = {
  getAll: () => apiClient<any[]>('/api/v1/products'),

  getById: (id: string) => apiClient<any>(`/api/v1/products/${id}`),

  create: (product: { name: string; sku: string; current_price: number }) =>
    apiClient<any>('/api/v1/products', {
      method: 'POST',
      body: JSON.stringify(product),
    }),
};

// Sentiment API calls
export const sentimentApi = {
  analyze: (productId: string, text: string) =>
    apiClient<any>('/api/v1/sentiment/analyze', {
      method: 'POST',
      body: JSON.stringify({ product_id: productId, text }),
    }),
};

// Pricing API calls
export const pricingApi = {
  getSuggestion: (productId: string) =>
    apiClient<any>(`/api/v1/pricing/suggestion/${productId}`),
};
