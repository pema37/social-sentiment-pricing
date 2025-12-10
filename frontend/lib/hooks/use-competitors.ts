// Competitor hooks
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { competitorsApi } from '@/lib/api';
import type { CreateCompetitorRequest, UpdateCompetitorRequest } from '@/types';

// Query keys
export const competitorKeys = {
  all: ['competitors'] as const,
  list: (params?: { skip?: number; limit?: number }) =>
    [...competitorKeys.all, 'list', params] as const,
  detail: (id: string) => [...competitorKeys.all, 'detail', id] as const,
  products: (competitorId: string) =>
    [...competitorKeys.all, 'products', competitorId] as const,
  priceHistory: (competitorProductId: string, params?: { days?: number }) =>
    [...competitorKeys.all, 'price-history', competitorProductId, params] as const,
};

// Get paginated competitors
export function useCompetitors(params?: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: competitorKeys.list(params),
    queryFn: () => competitorsApi.getAll(params),
    staleTime: 30 * 1000,
  });
}

// Get single competitor
export function useCompetitor(id: string | null) {
  return useQuery({
    queryKey: competitorKeys.detail(id || ''),
    queryFn: () => competitorsApi.getById(id!),
    enabled: !!id,
    staleTime: 30 * 1000,
  });
}

// Get competitor products
export function useCompetitorProducts(competitorId: string | null) {
  return useQuery({
    queryKey: competitorKeys.products(competitorId || ''),
    queryFn: () => competitorsApi.getProducts(competitorId!),
    enabled: !!competitorId,
    staleTime: 60 * 1000,
  });
}

// Get competitor product price history
export function useCompetitorPriceHistory(
  competitorProductId: string | null,
  params?: { days?: number }
) {
  return useQuery({
    queryKey: competitorKeys.priceHistory(competitorProductId || '', params),
    queryFn: () => competitorsApi.getPriceHistory(competitorProductId!, params),
    enabled: !!competitorProductId,
    staleTime: 60 * 1000,
  });
}

// Create competitor
export function useCreateCompetitor() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateCompetitorRequest) => competitorsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: competitorKeys.all });
    },
  });
}

// Update competitor
export function useUpdateCompetitor() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateCompetitorRequest }) =>
      competitorsApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: competitorKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: competitorKeys.list() });
    },
  });
}

// Delete competitor
export function useDeleteCompetitor() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => competitorsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: competitorKeys.all });
    },
  });
}
