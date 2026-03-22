// lib/hooks/use-products.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { productsApi } from '@/lib/api';
import { toast } from '@/lib/hooks/use-toast';
import { productKeys } from '@/lib/api/query-keys';
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

// Re-export keys for backwards compatibility (other files may import from here)
export { productKeys };

// ─────────────────────────────────────────────────────────────────────────────
// Queries
// ─────────────────────────────────────────────────────────────────────────────

// Get paginated products
export function useProducts(params?: { page?: number; page_size?: number; search?: string }) {
  return useQuery({
    queryKey: productKeys.list(params),
    queryFn: () => productsApi.getAll(params),
    staleTime: 30 * 1000,
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 5000),
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

// Get price suggestion for a product (with AI explanation)
export function usePriceSuggestion(id: string | null, useAi: boolean = true) {
  return useQuery({
    queryKey: [...productKeys.priceSuggestion(id || ''), useAi],
    queryFn: () => productsApi.getSuggestion(id!, useAi),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
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
      queryClient.invalidateQueries({ queryKey: productKeys.lists() });
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
    
    onMutate: async (deletedId: string) => {
      await queryClient.cancelQueries({ queryKey: productKeys.all });
      
      const previousData = queryClient.getQueriesData({ queryKey: productKeys.all });
      
      queryClient.setQueriesData(
        { queryKey: productKeys.all },
        (old: PaginatedProducts | Product[] | undefined) => {
          if (!old) return old;
          
          if ('items' in old && Array.isArray(old.items)) {
            return {
              ...old,
              items: old.items.filter((p: Product) => p.id !== deletedId),
              total: Math.max(0, old.total - 1),
            };
          }
          
          if (Array.isArray(old)) {
            return old.filter((p: Product) => p.id !== deletedId);
          }
          
          return old;
        }
      );
      
      queryClient.removeQueries({ queryKey: productKeys.detail(deletedId) });
      
      return { previousData };
    },
    
    onSuccess: () => {
      toast.success({ title: 'Product deleted', message: 'Product has been removed' });
      
      setTimeout(() => {
        queryClient.invalidateQueries({ 
          queryKey: productKeys.all,
          refetchType: 'active',
        });
      }, 500);
    },
    
    onError: (error: Error, deletedId: string, context) => {
      if (context?.previousData) {
        context.previousData.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data);
        });
      }
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
      queryClient.invalidateQueries({ queryKey: productKeys.lists() });
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
    mutationFn: ({ id, price }: { id: string; price: number }) => {
      if (price == null || isNaN(price)) {
        return Promise.reject(new Error('Invalid price value'));
      }
      return productsApi.update(id, { current_price: price });
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: productKeys.priceSuggestion(variables.id) });
      queryClient.invalidateQueries({ queryKey: productKeys.lists() });
      toast.success({ 
        title: 'Price updated', 
        message: `Price has been updated to $${(variables.price ?? 0).toFixed(2)}` 
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


