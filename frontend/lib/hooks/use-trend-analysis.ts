'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  runTrendAnalysis,
  analyzeProductOpportunity,
  detectRisks,
  generateInsight,
  getQuickStats,
} from '@/lib/api/trend-analysis';
import { trendAnalysisKeys } from '@/lib/api/query-keys';
import { useToast } from '@/lib/hooks/use-toast';
import type { TrendAnalysisRequest } from '@/types/trend-analysis';

export function useQuickStats() {
  return useQuery({
    queryKey: trendAnalysisKeys.quickStats(),
    queryFn: getQuickStats,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
}

export function useTrendAnalysis(params?: TrendAnalysisRequest) {
  return useQuery({
    queryKey: trendAnalysisKeys.analysis(params as unknown as Record<string, unknown> | undefined),
    queryFn: () => runTrendAnalysis(params),
    staleTime: 5 * 60_000,
    enabled: false,
  });
}

export function useRunTrendAnalysis() {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: runTrendAnalysis,
    onSuccess: (data, variables) => {
      queryClient.setQueryData(
        trendAnalysisKeys.analysis(variables as unknown as Record<string, unknown>),
        data
      );
      success('AI trend analysis complete');
    },
    onError: (err) => {
      error('Failed to run trend analysis');
      console.error('Trend analysis error:', err);
    },
  });
}

export function useProductOpportunity(productId: string) {
  return useQuery({
    queryKey: trendAnalysisKeys.opportunity(productId),
    queryFn: () => analyzeProductOpportunity(productId),
    staleTime: 5 * 60_000,
    enabled: false,
  });
}

export function useAnalyzeProductOpportunity() {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: ({
      productId,
      useModel,
    }: {
      productId: string;
      useModel?: 'openai' | 'gemini';
    }) => analyzeProductOpportunity(productId, useModel),
    onSuccess: (data, { productId }) => {
      queryClient.setQueryData(trendAnalysisKeys.opportunity(productId), data);
      success('Product analysis complete');
    },
    onError: (err) => {
      error('Failed to analyze product');
      console.error('Product opportunity error:', err);
    },
  });
}

export function useRiskDetection() {
  return useQuery({
    queryKey: trendAnalysisKeys.risks(),
    queryFn: () => detectRisks(),
    staleTime: 5 * 60_000,
    enabled: false,
  });
}

export function useDetectRisks() {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: (useModel?: 'openai' | 'gemini') => detectRisks(useModel),
    onSuccess: (data) => {
      queryClient.setQueryData(trendAnalysisKeys.risks(), data);
      success(`Risk detection complete - found ${data.risks.length} risk(s)`);
    },
    onError: (err) => {
      error('Failed to detect risks');
      console.error('Risk detection error:', err);
    },
  });
}

export function useGenerateInsight() {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: ({
      days,
      useModel,
    }: {
      days?: number;
      useModel?: 'openai' | 'gemini';
    }) => generateInsight(days, useModel),
    onSuccess: (data, { days = 30 }) => {
      queryClient.setQueryData(trendAnalysisKeys.insight(days), data);
      success('Market insight generated');
    },
    onError: (err) => {
      error('Failed to generate insight');
      console.error('Insight generation error:', err);
    },
  });
}


