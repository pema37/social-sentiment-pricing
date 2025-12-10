// Product hooks
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { productsApi } from '@/lib/api';
import type { 
  Product,
  CreateProductRequest, 
  UpdateProductRequest,
  PaginatedProducts,
} from '@/types';

// Re-export types for convenience
export type { Product, CreateProductRequest, UpdateProductRequest, PaginatedProducts };

// Legacy type aliases for backwards compatibility
export type ProductCreate = CreateProductRequest;
export type ProductUpdate = UpdateProductRequest;

// Query keys
export const productKeys = {
  all: ['products'] as const,
  list: (params?: { page?: number; page_size?: number }) =>
    [...productKeys.all, 'list', params] as const,
  detail: (id: string) => [...productKeys.all, 'detail', id] as const,
  suggestion: (id: string) => [...productKeys.all, 'suggestion', id] as const,
  priceHistory: (id: string, params?: { days?: number }) =>
    [...productKeys.all, 'price-history', id, params] as const,
};

// Get paginated products
export function useProducts(params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: productKeys.list(params),
    queryFn: () => productsApi.getAll(params),
    staleTime: 30 * 1000,
  });
}

// Get single product
export function useProduct(id: string | null) {
  return useQuery({
    queryKey: productKeys.detail(id || ''),
    queryFn: () => productsApi.getById(id!),
    enabled: !!id,
    staleTime: 30 * 1000,
  });
}

// Get price suggestion for a product
export function usePriceSuggestion(id: string | null) {
  return useQuery({
    queryKey: productKeys.suggestion(id || ''),
    queryFn: () => productsApi.getSuggestion(id!),
    enabled: !!id,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Get price history for a product
export function usePriceHistory(id: string | null, params?: { days?: number; limit?: number }) {
  return useQuery({
    queryKey: productKeys.priceHistory(id || '', params),
    queryFn: () => productsApi.getPriceHistory(id!, params),
    enabled: !!id,
    staleTime: 60 * 1000,
  });
}

// Create product
export function useCreateProduct() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateProductRequest) => productsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.all });
    },
  });
}

// Update product
export function useUpdateProduct() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateProductRequest }) =>
      productsApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: productKeys.list() });
    },
  });
}

// Delete product
export function useDeleteProduct() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => productsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.all });
    },
  });
}

// Toggle auto-pricing for a product
export function useToggleAutoPricing() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      productsApi.update(id, { auto_pricing_enabled: enabled }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: productKeys.list() });
    },
  });
}

// Apply price suggestion
export function useApplyPriceSuggestion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, price }: { id: string; price: number }) =>
      productsApi.update(id, { current_price: price }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: productKeys.suggestion(variables.id) });
      queryClient.invalidateQueries({ queryKey: productKeys.list() });
    },
  });
}

// Bulk update auto-pricing
export function useBulkUpdatePricing() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ productIds, enabled }: { productIds: string[]; enabled: boolean }) =>
      productsApi.bulkUpdatePricing(productIds, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.all });
    },
  });
}
