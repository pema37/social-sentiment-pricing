// lib/hooks/use-products.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { productsApi } from '@/lib/api';
import { toast } from '@/lib/hooks/use-toast';
import type { 
  Product,
  CreateProductRequest, 
  UpdateProductRequest,
  PaginatedProducts,
} from '@/types';
import type { ImportProductRow, ImportProductsResponse } from '@/lib/api/products';

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

// ─────────────────────────────────────────────────────────────────────────────
// Queries
// ─────────────────────────────────────────────────────────────────────────────

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

// ─────────────────────────────────────────────────────────────────────────────
// Mutations
// ─────────────────────────────────────────────────────────────────────────────

// Create product
export function useCreateProduct() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateProductRequest) => productsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.all });
      toast.success({ title: 'Product created', message: 'Product has been created successfully' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to create product', message: error.message });
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
      toast.success({ title: 'Product updated', message: 'Product details have been saved' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to update product', message: error.message });
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
      toast.success({ title: 'Product deleted', message: 'Product has been removed' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to delete product', message: error.message });
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
      toast.success({
        title: variables.enabled ? 'Auto-pricing enabled' : 'Auto-pricing disabled',
        message: `Auto-pricing has been ${variables.enabled ? 'enabled' : 'disabled'} for this product`,
      });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to update auto-pricing', message: error.message });
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
      toast.success({ 
        title: 'Price updated', 
        message: `Price has been updated to $${variables.price.toFixed(2)}` 
      });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to apply price', message: error.message });
    },
  });
}

// Bulk update auto-pricing
export function useBulkUpdatePricing() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ productIds, enabled }: { productIds: string[]; enabled: boolean }) =>
      productsApi.bulkUpdatePricing(productIds, enabled),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.all });
      toast.success({
        title: 'Bulk update complete',
        message: `Auto-pricing ${variables.enabled ? 'enabled' : 'disabled'} for ${variables.productIds.length} products`,
      });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to update products', message: error.message });
    },
  });
}

// Import products from CSV
export function useImportProducts() {
  const queryClient = useQueryClient();

  return useMutation<ImportProductsResponse, Error, { products: ImportProductRow[] }>({
    mutationFn: (data) => productsApi.import(data),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: productKeys.all });
      
      if (result.failed > 0) {
        toast.warning({
          title: 'Import completed with errors',
          message: `${result.created} products imported, ${result.failed} failed`,
        });
      } else {
        toast.success({
          title: 'Import successful',
          message: `${result.created} products have been imported`,
        });
      }
    },
    onError: (error: Error) => {
      toast.error({ title: 'Import failed', message: error.message });
    },
  });
}
