// lib/api/products.ts

import { api } from './client';
import type {
  Product,
  PaginatedProducts,
  CreateProductRequest,
  UpdateProductRequest,
  PriceSuggestion,
  PriceHistoryEntry,
} from '@/types';

// ─────────────────────────────────────────────────────────────────────────────
// Types for Import
// ─────────────────────────────────────────────────────────────────────────────

export interface ImportProductRow {
  name: string;
  sku?: string;
  base_price: number;
  description?: string;
  category?: string;
  image_url?: string;
  stock_quantity?: number;
}

export interface ImportProductsRequest {
  products: ImportProductRow[];
}

export interface ImportProductsResponse {
  created: number;
  updated: number;
  skipped: number;
  failed: number;
  errors: string[];
}

// ─────────────────────────────────────────────────────────────────────────────
// API Functions
// ─────────────────────────────────────────────────────────────────────────────

export const productsApi = {
  getAll: (params?: { page?: number; page_size?: number; search?: string }) =>
    api.get<PaginatedProducts>('/api/v1/products', params),

  getById: (id: string) =>
    api.get<Product>(`/api/v1/products/${id}`),

  create: (data: CreateProductRequest) =>
    api.post<Product>('/api/v1/products', data),

  update: (id: string, data: UpdateProductRequest) =>
    api.patch<Product>(`/api/v1/products/${id}`, data),

  delete: (id: string) =>
    api.delete<void>(`/api/v1/products/${id}`),

  getSuggestion: (id: string, useAi: boolean = true) =>
    api.get<PriceSuggestion>(`/api/v1/products/${id}/price-suggestion?use_ai=${useAi}`),

  getPriceHistory: (id: string, params?: { days?: number; limit?: number }) =>
    api.get<PriceHistoryEntry[]>(`/api/v1/products/${id}/price-history`, params),

  bulkUpdatePricing: (productIds: string[], enabled: boolean) =>
    api.post<{ updated_count: number }>('/api/v1/products/bulk/auto-pricing', {
      product_ids: productIds,
      enabled,
    }),

  import: (data: ImportProductsRequest) =>
    api.post<ImportProductsResponse>('/api/v1/products/import', data),

  generateDescription: (id: string, options: { tone: string; length: string }) =>
    api.post(`/api/v1/products/${id}/generate-description`, options),
};

