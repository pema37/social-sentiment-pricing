// Products API
import { api } from './client';
import type {
  Product,
  PaginatedProducts,
  CreateProductRequest,
  UpdateProductRequest,
  PriceSuggestion,
  PriceHistoryEntry,
} from '@/types';

export const productsApi = {
  getAll: (params?: { page?: number; page_size?: number }) =>
    api.get<PaginatedProducts>('/api/v1/products', params),

  getById: (id: string) =>
    api.get<Product>(`/api/v1/products/${id}`),

  create: (data: CreateProductRequest) =>
    api.post<Product>('/api/v1/products', data),

  update: (id: string, data: UpdateProductRequest) =>
    api.patch<Product>(`/api/v1/products/${id}`, data),

  delete: (id: string) =>
    api.delete<void>(`/api/v1/products/${id}`),

  // Price suggestion
  getSuggestion: (id: string) =>
    api.get<PriceSuggestion>(`/api/v1/products/${id}/price-suggestion`),

  // Price history
  getPriceHistory: (id: string, params?: { days?: number; limit?: number }) =>
    api.get<PriceHistoryEntry[]>(`/api/v1/products/${id}/price-history`, params),

  // Bulk operations
  bulkUpdatePricing: (productIds: string[], enabled: boolean) =>
    api.post<{ updated_count: number }>('/api/v1/products/bulk/auto-pricing', {
      product_ids: productIds,
      enabled,
    }),
};
