// Competitors API
import { api } from './client';
import type {
  Competitor,
  PaginatedCompetitors,
  CreateCompetitorRequest,
  UpdateCompetitorRequest,
  CompetitorProduct,
  CompetitorPriceHistory,
} from '@/types';

export const competitorsApi = {
  // Get all competitors
  getAll: (params?: { skip?: number; limit?: number }) =>
    api.get<PaginatedCompetitors>('/api/v1/competitors', params),

  // Get single competitor
  getById: (id: string) =>
    api.get<Competitor>(`/api/v1/competitors/${id}`),

  // Create competitor
  create: (data: CreateCompetitorRequest) =>
    api.post<Competitor>('/api/v1/competitors', data),

  // Update competitor
  update: (id: string, data: UpdateCompetitorRequest) =>
    api.patch<Competitor>(`/api/v1/competitors/${id}`, data),

  // Delete competitor
  delete: (id: string) =>
    api.delete<void>(`/api/v1/competitors/${id}`),

  // Get competitor products
  getProducts: (competitorId: string) =>
    api.get<CompetitorProduct[]>(`/api/v1/competitors/${competitorId}/products`),

  // Get price history for a competitor product
  getPriceHistory: (competitorProductId: string, params?: { days?: number }) =>
    api.get<CompetitorPriceHistory[]>(
      `/api/v1/competitors/products/${competitorProductId}/price-history`,
      params
    ),
};
