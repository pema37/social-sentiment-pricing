// frontend/lib/hooks/use-intelligence.ts
// React Query hooks for Intelligence Environment dashboard
// Pattern: matches use-outcomes.ts, use-analytics.ts

import { useQuery } from '@tanstack/react-query';
import { intelligenceApi } from '@/lib/api/intelligence';
import type { DriftSeverity } from '@/types/intelligence';

// ── Query Keys ──

export const intelligenceKeys = {
  all: ['intelligence'] as const,
  dashboard: (topN: number) => [...intelligenceKeys.all, 'dashboard', topN] as const,
  health: () => [...intelligenceKeys.all, 'health'] as const,
  experiments: (categoryId?: string) =>
    [...intelligenceKeys.all, 'experiments', categoryId ?? 'all'] as const,
  experiment: (categoryId: string) =>
    [...intelligenceKeys.all, 'experiment', categoryId] as const,
  calibration: (categoryId?: string) =>
    [...intelligenceKeys.all, 'calibration', categoryId ?? 'global'] as const,
  driftAlerts: (severity?: DriftSeverity) =>
    [...intelligenceKeys.all, 'drift-alerts', severity ?? 'all'] as const,
  categories: (params?: Record<string, unknown>) =>
    [...intelligenceKeys.all, 'categories', params] as const,
  category: (categoryId: string) =>
    [...intelligenceKeys.all, 'category', categoryId] as const,
};

// ── Combined Dashboard (single API call) ──

export function useIEDashboard(topN = 10) {
  return useQuery({
    queryKey: intelligenceKeys.dashboard(topN),
    queryFn: () => intelligenceApi.dashboard(topN),
    staleTime: 60 * 1000, // 1 min — health data refreshes frequently
  });
}

// ── Individual Endpoints ──

export function useIEHealth() {
  return useQuery({
    queryKey: intelligenceKeys.health(),
    queryFn: () => intelligenceApi.health(),
    staleTime: 60 * 1000, // match refetchInterval to avoid extra background fetches
    refetchInterval: 60 * 1000, // auto-refresh every 60s
  });
}

export function useExperiments(categoryId?: string) {
  return useQuery({
    queryKey: intelligenceKeys.experiments(categoryId),
    queryFn: () => intelligenceApi.experiments(categoryId),
    staleTime: 5 * 60 * 1000, // 5 min — experiments change slowly
  });
}

export function useExperiment(categoryId: string | undefined) {
  return useQuery({
    queryKey: intelligenceKeys.experiment(categoryId ?? ''),
    queryFn: () => intelligenceApi.experiment(categoryId!),
    enabled: !!categoryId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCalibration(categoryId?: string) {
  return useQuery({
    queryKey: intelligenceKeys.calibration(categoryId),
    queryFn: () => intelligenceApi.calibration(categoryId),
    staleTime: 10 * 60 * 1000, // 10 min — calibration changes slowly
  });
}

export function useDriftAlerts(severity?: DriftSeverity) {
  return useQuery({
    queryKey: intelligenceKeys.driftAlerts(severity),
    queryFn: () => intelligenceApi.driftAlerts({ severity, active_only: true }),
    staleTime: 60 * 1000,
    refetchInterval: 2 * 60 * 1000, // auto-refresh every 2 min
  });
}

export function useCategoryPerformance(params?: {
  min_recommendations?: number;
  sort_by?: string;
}) {
  return useQuery({
    queryKey: intelligenceKeys.categories(params),
    queryFn: () => intelligenceApi.categories(params),
    staleTime: 5 * 60 * 1000,
  });
}

export function useCategoryDetail(categoryId: string | undefined) {
  return useQuery({
    queryKey: intelligenceKeys.category(categoryId ?? ''),
    queryFn: () => intelligenceApi.category(categoryId!),
    enabled: !!categoryId,
    staleTime: 5 * 60 * 1000,
  });
}


