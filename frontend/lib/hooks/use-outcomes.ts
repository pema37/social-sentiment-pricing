// ============================================
// OUTCOME HOOKS (React Query)
//
// Follows existing pattern: use-products.ts, use-pricing.ts, etc.
// Place at: frontend/lib/hooks/use-outcomes.ts
// Re-export from: frontend/lib/hooks/index.ts
//
// Add to index.ts:
//   export * from './use-outcomes';
// ============================================

import { useQuery } from '@tanstack/react-query';
import { outcomesApi, transformOutcomeToCard, getBestLift } from '@/lib/api/outcomes';
/* eslint-disable @typescript-eslint/no-unused-vars */
import type {
  OutcomeListParams,
  OutcomeCardData,
  RecommendationOutcome,
  ConfidenceCalibration,
  MerchantModificationPattern,
  CategoryBenchmark,
  DataGapFailureRate,
  ElasticityAccuracy,
  AccuracyStats,
} from '@/types/outcome';
/* eslint-enable @typescript-eslint/no-unused-vars */
// ── Query Keys ──

export const outcomeKeys = {
  all: ['outcomes'] as const,
  lists: () => [...outcomeKeys.all, 'list'] as const,
  list: (params: OutcomeListParams) => [...outcomeKeys.lists(), params] as const,
  detail: (id: string) => [...outcomeKeys.all, 'detail', id] as const,
  accuracy: (days: number) => [...outcomeKeys.all, 'accuracy', days] as const,
  calibration: (params: Record<string, unknown>) => [...outcomeKeys.all, 'calibration', params] as const,
  merchantPatterns: (params: Record<string, unknown>) => [...outcomeKeys.all, 'merchant-patterns', params] as const,
  benchmarks: (category: string, days: number) => [...outcomeKeys.all, 'benchmarks', category, days] as const,
  dataGaps: (days: number) => [...outcomeKeys.all, 'data-gaps', days] as const,
  elasticityAccuracy: (params: Record<string, unknown>) => [...outcomeKeys.all, 'elasticity-accuracy', params] as const,
  rulePerformance: (ruleId: string, days: number) => [...outcomeKeys.all, 'rule-performance', ruleId, days] as const,
};

// ── List Outcomes ──

export function useOutcomes(params: OutcomeListParams = {}) {
  return useQuery({
    queryKey: outcomeKeys.list(params),
    queryFn: () => outcomesApi.list(params),
  });
}

/** List outcomes pre-transformed to card format. */
export function useOutcomeCards(params: OutcomeListParams = {}) {
  return useQuery({
    queryKey: [...outcomeKeys.list(params), 'cards'],
    queryFn: async (): Promise<OutcomeCardData[]> => {
      const outcomes = await outcomesApi.list(params);
      return outcomes.map(transformOutcomeToCard);
    },
  });
}

// ── Single Outcome ──

export function useOutcome(outcomeId: string | undefined) {
  return useQuery({
    queryKey: outcomeKeys.detail(outcomeId ?? ''),
    queryFn: () => outcomesApi.get(outcomeId!),
    enabled: !!outcomeId,
  });
}

// ── Accuracy Stats ──

export function useAccuracyStats(days = 30) {
  return useQuery({
    queryKey: outcomeKeys.accuracy(days),
    queryFn: () => outcomesApi.accuracyStats(days),
  });
}

// ── Intelligence Environment Hooks ──

/** Confidence calibration — target Pearson r > 0.7 by Month 12. */
export function useConfidenceCalibration(params: {
  product_category?: string;
  days?: number;
} = {}) {
  return useQuery({
    queryKey: outcomeKeys.calibration(params),
    queryFn: () => outcomesApi.confidenceCalibration(params),
    staleTime: 5 * 60 * 1000, // 5 min — calibration changes slowly
  });
}

/** Merchant modification patterns — backward learning for Strategist. */
export function useMerchantPatterns(params: {
  product_category?: string;
  days?: number;
} = {}) {
  return useQuery({
    queryKey: outcomeKeys.merchantPatterns(params),
    queryFn: () => outcomesApi.merchantModificationPattern(params),
    staleTime: 5 * 60 * 1000,
  });
}

/** Category benchmarks — cross-merchant intelligence. */
export function useCategoryBenchmarks(category: string | undefined, days = 90) {
  return useQuery({
    queryKey: outcomeKeys.benchmarks(category ?? '', days),
    queryFn: () => outcomesApi.categoryBenchmarks(category!, days),
    enabled: !!category,
    staleTime: 10 * 60 * 1000, // 10 min — benchmarks change slowly
  });
}

/** Data gap failure rates — backward learning for Scout. */
export function useDataGapFailureRates(days = 90) {
  return useQuery({
    queryKey: outcomeKeys.dataGaps(days),
    queryFn: () => outcomesApi.dataGapFailureRates(days),
    staleTime: 5 * 60 * 1000,
  });
}

/** Elasticity accuracy — backward learning for Analyst. */
export function useElasticityAccuracy(params: {
  product_category?: string;
  days?: number;
} = {}) {
  return useQuery({
    queryKey: outcomeKeys.elasticityAccuracy(params),
    queryFn: () => outcomesApi.elasticityAccuracy(params),
    staleTime: 5 * 60 * 1000,
  });
}

/** Rule performance — single rule drill-down. */
export function useRulePerformance(ruleId: string | undefined, days = 90) {
  return useQuery({
    queryKey: outcomeKeys.rulePerformance(ruleId ?? '', days),
    queryFn: () => outcomesApi.rulePerformance(ruleId!, days),
    enabled: !!ruleId,
  });
}

// ── Derived / Computed Hooks ──

/** 
 * Dashboard-level outcome summary.
 * Combines accuracy stats with calibration status. 
 */
export function useOutcomeDashboard(days = 30) {
  const accuracy = useAccuracyStats(days);
  const calibration = useConfidenceCalibration({ days: 90 });

  return {
    accuracy: accuracy.data,
    calibration: calibration.data,
    isLoading: accuracy.isLoading || calibration.isLoading,
    isError: accuracy.isError || calibration.isError,
  };
}

/**
 * Best lift across all outcomes for a product.
 * Useful for product detail page headline metric.
 */
export function useProductBestLift(productId: string | undefined) {
  const { data: outcomes } = useOutcomes({
    product_id: productId,
    days: 90,
    limit: 10,
  });

  if (!outcomes?.length) {
    return { lift: null, window: 'none', outcomeCount: 0 };
  }

  // Find outcome with best measured lift
  let best: { lift: number | null; window: string } = { lift: null, window: 'none' };
  for (const outcome of outcomes) {
    const candidate = getBestLift(outcome);
    if (candidate.lift !== null && (best.lift === null || candidate.lift > best.lift)) {
      best = candidate;
    }
  }

  return { ...best, outcomeCount: outcomes.length };
}


