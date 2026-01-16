// Competitors API
import { api } from './client';
import type {
  Competitor,
  PaginatedCompetitors,
  CreateCompetitorRequest,
  UpdateCompetitorRequest,
  CompetitorProduct,
  PaginatedCompetitorProducts,
  CompetitorProductWithDetails,
  CreateCompetitorProductRequest,
  UpdateCompetitorProductRequest,
  CompetitorPriceHistory,
  CompetitorPriceComparison,
  // NEW: Matching types
  CompetitorSearchRequest,
  CompetitorSearchResponse,
  ProductMatchRequest,
  BulkMatchRequest,
  BulkMatchResponse,
  ProvidersListResponse,
  CacheClearResponse,
} from '@/types';

export const competitorsApi = {
  // ============== Competitors ==============

  // Get all competitors
  getAll: (params?: { page?: number; page_size?: number; is_active?: boolean }) =>
    api.get<PaginatedCompetitors>('/api/v1/competitors/', params),

  // Get single competitor
  getById: (id: string) =>
    api.get<Competitor>(`/api/v1/competitors/${id}`),

  // Create competitor
  create: (data: CreateCompetitorRequest) =>
    api.post<Competitor>('/api/v1/competitors/', data),

  // Update competitor
  update: (id: string, data: UpdateCompetitorRequest) =>
    api.patch<Competitor>(`/api/v1/competitors/${id}`, data),

  // Delete competitor
  delete: (id: string) =>
    api.delete<void>(`/api/v1/competitors/${id}`),

  // ============== Competitor Products ==============

  // List competitor products
  getProducts: (params?: { 
    product_id?: string; 
    competitor_id?: string; 
    is_active?: boolean;
    page?: number;
    page_size?: number;
  }) =>
    api.get<PaginatedCompetitorProducts>('/api/v1/competitors/products/', params),

  // Get single competitor product with details
  getProduct: (competitorProductId: string) =>
    api.get<CompetitorProductWithDetails>(`/api/v1/competitors/products/${competitorProductId}`),

  // Create competitor product link
  createProduct: (data: CreateCompetitorProductRequest) =>
    api.post<CompetitorProduct>('/api/v1/competitors/products/', data),

  // Update competitor product
  updateProduct: (competitorProductId: string, data: UpdateCompetitorProductRequest) =>
    api.patch<CompetitorProduct>(`/api/v1/competitors/products/${competitorProductId}`, data),

  // Delete competitor product
  deleteProduct: (competitorProductId: string) =>
    api.delete<void>(`/api/v1/competitors/products/${competitorProductId}`),

  // ============== Price History & Scraping ==============

  // Trigger price scrape
  scrapePrice: (competitorProductId: string) =>
    api.post<CompetitorPriceHistory>(`/api/v1/competitors/products/${competitorProductId}/scrape`),

  // Get price history
  getPriceHistory: (competitorProductId: string, params?: { days?: number }) =>
    api.get<{ items: CompetitorPriceHistory[]; total: number }>(
      `/api/v1/competitors/products/${competitorProductId}/history`,
      params
    ),

  // ============== Analysis ==============

  // Compare prices for a product
  comparePrices: (productId: string) =>
    api.get<CompetitorPriceComparison>(`/api/v1/competitors/compare/${productId}`),

  // ============== NEW: Auto URL Matching ==============

  /**
   * Search for competitor products by name
   * Uses Google Shopping, Custom Search, and DuckDuckGo
   */
  searchCompetitors: (data: CompetitorSearchRequest) =>
    api.post<CompetitorSearchResponse>('/api/v1/competitors/match/search', data),

  /**
   * Find competitors for a specific product in your catalog
   * Optionally auto-links high-confidence matches
   */
  matchProduct: (data: ProductMatchRequest) =>
    api.post<CompetitorSearchResponse>('/api/v1/competitors/match/product', data),

  /**
   * Bulk match multiple products at once
   */
  bulkMatch: (data: BulkMatchRequest) =>
    api.post<BulkMatchResponse>('/api/v1/competitors/match/bulk', data),

  /**
   * Get list of available search providers
   */
  getProviders: () =>
    api.get<ProvidersListResponse>('/api/v1/competitors/match/providers'),

  /**
   * Clear the search cache
   */
  clearCache: () =>
    api.post<CacheClearResponse>('/api/v1/competitors/match/clear-cache'),
};



