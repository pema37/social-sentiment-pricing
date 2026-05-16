'use client';

// Sentiment hooks
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { sentimentApi } from '@/lib/api';
import { sentimentKeys, analyticsKeys } from '@/lib/api/query-keys';
import type { AnalyzeRequest } from '@/types';

// Query keys (re-export from centralized registry for backwards compatibility)
export { sentimentKeys };

// Get sentiment results for a product
export function useSentimentByProduct(productId: string | null) {
  return useQuery({
    queryKey: sentimentKeys.productSentiment(productId || ''),
    queryFn: () => sentimentApi.getByProduct(productId!),
    enabled: !!productId,
    staleTime: 60 * 1000,
    refetchOnMount: true,
  });
}

// Get mentions for a product
export function useMentions(
  productId: string | null,
  params: { page?: number; page_size?: number } = {}
) {
  return useQuery({
    queryKey: sentimentKeys.mentions({ productId, ...params }),
    queryFn: () => sentimentApi.getMentions(productId!, params),
    enabled: !!productId,
    staleTime: 60 * 1000,
    refetchOnMount: true,
  });
}

// Analyze text sentiment and save to database
export function useAnalyzeSentiment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AnalyzeRequest) => sentimentApi.analyze(data),
    onSuccess: (_data, variables) => {
      const productId = variables.product_id;
      
      queryClient.invalidateQueries({
        queryKey: sentimentKeys.mentions({ productId }),
      });
      
      queryClient.invalidateQueries({
        queryKey: sentimentKeys.productSentiment(productId),
      });
      
      queryClient.invalidateQueries({ queryKey: analyticsKeys.all });
    },
  });
}




