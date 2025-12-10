// Sentiment hooks
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { sentimentApi } from '@/lib/api';
import type { AnalyzeRequest } from '@/types';

// Query keys
export const sentimentKeys = {
  all: ['sentiment'] as const,
  byProduct: (productId: string) => [...sentimentKeys.all, 'product', productId] as const,
  mentions: (productId: string, params?: { page?: number; page_size?: number }) =>
    [...sentimentKeys.all, 'mentions', productId, params] as const,
};

// Get sentiment results for a product
export function useSentimentByProduct(productId: string | null) {
  return useQuery({
    queryKey: sentimentKeys.byProduct(productId || ''),
    queryFn: () => sentimentApi.getByProduct(productId!),
    enabled: !!productId,
    staleTime: 60 * 1000,
  });
}

// Get mentions for a product
export function useMentions(
  productId: string | null,
  params: { page?: number; page_size?: number } = {}
) {
  return useQuery({
    queryKey: sentimentKeys.mentions(productId || '', params),
    queryFn: () => sentimentApi.getMentions(productId!, params),
    enabled: !!productId,
    staleTime: 60 * 1000,
  });
}

// Analyze text sentiment
export function useAnalyzeSentiment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AnalyzeRequest) => sentimentApi.analyze(data),
    onSuccess: (data) => {
      // Invalidate mentions for this product
      queryClient.invalidateQueries({
        queryKey: sentimentKeys.mentions(data.product_id),
      });
      // Invalidate sentiment by product
      queryClient.invalidateQueries({
        queryKey: sentimentKeys.byProduct(data.product_id),
      });
      // Invalidate analytics to update charts
      queryClient.invalidateQueries({ queryKey: ['analytics'] });
    },
  });
}
