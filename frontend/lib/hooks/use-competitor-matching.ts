// frontend/lib/hooks/use-competitor-matching.ts

/**
 * React Query hooks for Competitor Matching feature
 * 
 * Provides hooks for:
 * - Searching for competitor products
 * - Matching products from your catalog
 * - Bulk matching multiple products
 * - Managing search providers
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { competitorsApi } from '@/lib/api/competitors';
import { useToast } from '@/lib/hooks/use-toast';
import type {
  CompetitorSearchRequest,
  CompetitorSearchResponse,
  ProductMatchRequest,
  BulkMatchRequest,
  BulkMatchResponse,
  ProvidersListResponse,
  MatchedProduct,
} from '@/types';

// ============================================
// QUERY KEYS
// ============================================

export const matchingKeys = {
  all: ['competitor-matching'] as const,
  providers: () => [...matchingKeys.all, 'providers'] as const,
  search: (query: string) => [...matchingKeys.all, 'search', query] as const,
  product: (productId: string) => [...matchingKeys.all, 'product', productId] as const,
};

// ============================================
// QUERIES
// ============================================

/**
 * Get available search providers
 */
export function useSearchProviders() {
  return useQuery({
    queryKey: matchingKeys.providers(),
    queryFn: () => competitorsApi.getProviders(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// ============================================
// MUTATIONS
// ============================================

/**
 * Search for competitor products by name
 * 
 * Usage:
 * ```tsx
 * const { mutate: search, data, isPending } = useCompetitorSearch();
 * search({ product_name: "iPhone 15 Pro", max_results: 10 });
 * ```
 */
export function useCompetitorSearch() {
  const toast = useToast();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CompetitorSearchRequest) => 
      competitorsApi.searchCompetitors(data),
    onSuccess: (response) => {
      if (response.success) {
        toast.success({
          title: 'Search Complete',
          message: `Found ${response.total_found} competitor${response.total_found !== 1 ? 's' : ''}`,
        });
      } else {
        toast.warning({
          title: 'Search Completed',
          message: response.providers_failed.length > 0 
            ? `Errors: ${response.providers_failed.join(', ')}`
            : 'No results found',
        });
      }
    },
    onError: (error: Error) => {
      toast.error({
        title: 'Search Failed',
        message: error.message || 'Failed to search for competitors',
      });
    },
  });
}

/**
 * Find competitors for a specific product
 * 
 * Usage:
 * ```tsx
 * const { mutate: match, isPending } = useProductMatch();
 * match({ product_id: "123", auto_link: true, auto_link_threshold: 0.8 });
 * ```
 */
export function useProductMatch() {
  const toast = useToast();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ProductMatchRequest) => 
      competitorsApi.matchProduct(data),
    onSuccess: (response, variables) => {
      if (response.success && response.total_found > 0) {
        toast.success({
          title: 'Matches Found',
          message: `Found ${response.total_found} competitor match${response.total_found !== 1 ? 'es' : ''}`,
        });
        
        // Invalidate competitor products if auto-link was enabled
        if (variables.auto_link) {
          queryClient.invalidateQueries({ queryKey: ['competitor-products'] });
          queryClient.invalidateQueries({ queryKey: ['competitors'] });
        }
      } else {
        toast.info({
          title: 'No Matches',
          message: 'No competitor matches found for this product',
        });
      }
    },
    onError: (error: Error) => {
      toast.error({
        title: 'Match Failed',
        message: error.message || 'Failed to find competitors',
      });
    },
  });
}

/**
 * Bulk match multiple products
 * 
 * Usage:
 * ```tsx
 * const { mutate: bulkMatch, isPending } = useBulkMatch();
 * bulkMatch({ product_ids: ["123", "456"], auto_link: true });
 * ```
 */
export function useBulkMatch() {
  const toast = useToast();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: BulkMatchRequest) => 
      competitorsApi.bulkMatch(data),
    onSuccess: (response, variables) => {
      const successCount = Object.values(response.results).filter(r => r.success).length;
      const totalCount = response.total_products;
      
      if (successCount === totalCount) {
        toast.success({
          title: 'Bulk Match Complete',
          message: `Successfully matched all ${totalCount} products`,
        });
      } else if (successCount > 0) {
        toast.warning({
          title: 'Partial Success',
          message: `Matched ${successCount} of ${totalCount} products`,
        });
      } else {
        toast.error({
          title: 'Bulk Match Failed',
          message: 'Failed to match any products',
        });
      }

      // Invalidate if auto-link was enabled
      if (variables.auto_link) {
        queryClient.invalidateQueries({ queryKey: ['competitor-products'] });
        queryClient.invalidateQueries({ queryKey: ['competitors'] });
      }
    },
    onError: (error: Error) => {
      toast.error({
        title: 'Bulk Match Failed',
        message: error.message || 'Bulk match failed',
      });
    },
  });
}

/**
 * Clear the search cache
 */
export function useClearMatchCache() {
  const toast = useToast();

  return useMutation({
    mutationFn: () => competitorsApi.clearCache(),
    onSuccess: (response) => {
      toast.success({
        title: 'Cache Cleared',
        message: `Cleared ${response.entries_cleared} cached searches`,
      });
    },
    onError: (error: Error) => {
      toast.error({
        title: 'Clear Failed',
        message: error.message || 'Failed to clear cache',
      });
    },
  });
}

// ============================================
// HELPER HOOKS
// ============================================

/**
 * Hook to get confidence level info
 */
export function useConfidenceLevel(score: number): {
  level: 'high' | 'medium' | 'low';
  color: string;
  label: string;
} {
  if (score >= 0.8) {
    return { level: 'high', color: 'green', label: 'High Match' };
  } else if (score >= 0.5) {
    return { level: 'medium', color: 'yellow', label: 'Possible Match' };
  } else {
    return { level: 'low', color: 'gray', label: 'Low Match' };
  }
}

/**
 * Filter and sort matched products
 */
export function useFilteredMatches(
  products: MatchedProduct[] | undefined,
  options?: {
    minConfidence?: number;
    merchants?: string[];
    hasPrice?: boolean;
    inStockOnly?: boolean;
  }
): MatchedProduct[] {
  if (!products) return [];

  let filtered = [...products];

  // Filter by confidence
  if (options?.minConfidence !== undefined) {
    filtered = filtered.filter(p => p.confidence_score >= options.minConfidence!);
  }

  // Filter by merchants
  if (options?.merchants && options.merchants.length > 0) {
    const merchantsLower = options.merchants.map(m => m.toLowerCase());
    filtered = filtered.filter(p => 
      merchantsLower.some(m => 
        p.merchant.toLowerCase().includes(m) || 
        p.merchant_domain.toLowerCase().includes(m)
      )
    );
  }

  // Filter by has price
  if (options?.hasPrice) {
    filtered = filtered.filter(p => p.price !== null);
  }

  // Filter by in stock
  if (options?.inStockOnly) {
    filtered = filtered.filter(p => p.in_stock);
  }

  // Sort by confidence (highest first)
  return filtered.sort((a, b) => b.confidence_score - a.confidence_score);
}



