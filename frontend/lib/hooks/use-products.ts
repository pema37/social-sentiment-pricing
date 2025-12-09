// lib/hooks/use-products.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';

// ─────────────────────────────── Types ─────────────────────────────── //

export interface Product {
  id: string;
  user_id: string;
  name: string;
  sku: string | null;
  description: string | null;
  category: string | null;
  image_url: string | null;
  is_active: boolean;
  base_price: number;
  current_price: number;
  cost: number | null;
  min_price: number | null;
  max_price: number | null;
  sentiment_multiplier: number;
  auto_pricing_enabled: boolean;
  keywords: string[];
  created_at: string;
  updated_at: string;
}

export interface ProductCreate {
  name: string;
  sku?: string | null;
  description?: string | null;
  category?: string | null;
  image_url?: string | null;
  is_active?: boolean;
  base_price: number;
  cost?: number | null;
  min_price?: number | null;
  max_price?: number | null;
  sentiment_multiplier?: number;
  auto_pricing_enabled?: boolean;
  keywords?: string[];
}

export interface ProductUpdate {
  name?: string;
  sku?: string | null;
  description?: string | null;
  category?: string | null;
  image_url?: string | null;
  is_active?: boolean;
  base_price?: number;
  current_price?: number;
  cost?: number | null;
  min_price?: number | null;
  max_price?: number | null;
  sentiment_multiplier?: number;
  auto_pricing_enabled?: boolean;
  keywords?: string[];
}

export interface PriceSuggestion {
  product_id: string;
  current_price: number;
  suggested_price: number;
  price_change: number;
  price_change_percent: number;
  sentiment_score: number;
  mention_volume: number;
  confidence: number;
  reasoning: string;
  factors: {
    sentiment_impact: number;
    volume_impact: number;
    competitor_impact: number;
    trend_impact: number;
  };
}

export interface PaginatedProducts {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ProductsParams {
  page?: number;
  page_size?: number;
}

export interface PriceHistoryItem {
  id: string;
  product_id: string;
  price: number;
  previous_price: number | null;
  change_percent: number | null;
  change_reason: string | null;
  created_at: string;
}

export interface PriceHistoryParams {
  days?: number;
  limit?: number;
}

// ─────────────────────────────── Query Keys ─────────────────────────────── //

export const productKeys = {
  all: ['products'] as const,
  lists: () => [...productKeys.all, 'list'] as const,
  list: (params: ProductsParams) => [...productKeys.lists(), params] as const,
  details: () => [...productKeys.all, 'detail'] as const,
  detail: (id: string) => [...productKeys.details(), id] as const,
  priceSuggestion: (id: string) => [...productKeys.all, 'price-suggestion', id] as const,
  priceHistory: (id: string, params?: PriceHistoryParams) => [...productKeys.all, 'price-history', id, params] as const,
};

// ─────────────────────────────── Queries ─────────────────────────────── //

/**
 * Fetch paginated list of products
 */
export function useProducts(params: ProductsParams = {}) {
  const { page = 1, page_size = 10 } = params;
  
  return useQuery({
    queryKey: productKeys.list({ page, page_size }),
    queryFn: async () => {
      const response = await apiClient<PaginatedProducts>(
        `/api/v1/products?page=${page}&page_size=${page_size}`
      );
      if (response.error) {
        throw new Error(response.error);
      }
      return response.data!;
    },
  });
}

/**
 * Fetch a single product by ID
 */
export function useProduct(productId: string | null) {
  return useQuery({
    queryKey: productKeys.detail(productId ?? ''),
    queryFn: async () => {
      if (!productId) throw new Error('Product ID required');
      const response = await apiClient<Product>(`/api/v1/products/${productId}`);
      if (response.error) {
        throw new Error(response.error);
      }
      return response.data!;
    },
    enabled: !!productId,
  });
}

/**
 * Fetch price suggestion for a product
 */
export function usePriceSuggestion(productId: string | null) {
  return useQuery({
    queryKey: productKeys.priceSuggestion(productId ?? ''),
    queryFn: async () => {
      if (!productId) throw new Error('Product ID required');
      const response = await apiClient<PriceSuggestion>(
        `/api/v1/products/${productId}/price-suggestion`
      );
      if (response.error) {
        throw new Error(response.error);
      }
      return response.data!;
    },
    enabled: !!productId,
  });
}

/**
 * Fetch price history for a product
 */
export function usePriceHistory(productId: string | null, params: PriceHistoryParams = {}) {
  const { days = 30, limit = 100 } = params;
  
  return useQuery({
    queryKey: productKeys.priceHistory(productId ?? '', { days, limit }),
    queryFn: async () => {
      if (!productId) throw new Error('Product ID required');
      const response = await apiClient<PriceHistoryItem[]>(
        `/api/v1/products/${productId}/price-history?days=${days}&limit=${limit}`
      );
      if (response.error) {
        throw new Error(response.error);
      }
      return response.data!;
    },
    enabled: !!productId,
  });
}

// ─────────────────────────────── Mutations ─────────────────────────────── //

/**
 * Create a new product
 */
export function useCreateProduct() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data: ProductCreate) => {
      const response = await apiClient<Product>('/api/v1/products', {
        method: 'POST',
        body: data,
      });
      if (response.error) {
        throw new Error(response.error);
      }
      return response.data!;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() });
    },
  });
}

/**
 * Update an existing product
 */
export function useUpdateProduct() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: ProductUpdate }) => {
      const response = await apiClient<Product>(`/api/v1/products/${id}`, {
        method: 'PATCH',
        body: data,
      });
      if (response.error) {
        throw new Error(response.error);
      }
      return response.data!;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() });
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.id) });
    },
  });
}

/**
 * Delete a product
 */
export function useDeleteProduct() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (productId: string) => {
      const response = await apiClient(`/api/v1/products/${productId}`, {
        method: 'DELETE',
      });
      if (response.error) {
        throw new Error(response.error);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() });
    },
  });
}

/**
 * Toggle auto-pricing for a product
 */
export function useToggleAutoPricing() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) => {
      const response = await apiClient<Product>(`/api/v1/products/${id}`, {
        method: 'PATCH',
        body: { auto_pricing_enabled: enabled },
      });
      if (response.error) {
        throw new Error(response.error);
      }
      return response.data!;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() });
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.id) });
    },
  });
}

/**
 * Apply a price suggestion to a product
 */
export function useApplyPriceSuggestion() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ id, newPrice }: { id: string; newPrice: number }) => {
      const response = await apiClient<Product>(`/api/v1/products/${id}`, {
        method: 'PATCH',
        body: { current_price: newPrice },
      });
      if (response.error) {
        throw new Error(response.error);
      }
      return response.data!;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() });
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: productKeys.priceSuggestion(variables.id) });
    },
  });
}
