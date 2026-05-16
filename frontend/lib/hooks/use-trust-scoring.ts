'use client';

// frontend/lib/hooks/use-trust-scoring.ts

/**
 * React Query hooks for Trust Scoring / Bot Detection
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { trustScoringApi } from '@/lib/api/trust-scoring';
import { useToast } from '@/lib/hooks/use-toast';
import type {
  AuthorScoreRequest,
  BatchAuthorScoreRequest,
  ContentAnalysisRequest,
  BatchContentAnalysisRequest,
  CampaignDetectionRequest,
  WeightedSentimentRequest,
  QuickSpamCheckRequest,
  QuickTrustCheckRequest,
  TrustLevel,
  RiskFlag,
  TrustLevelInfo,
  RiskFlagInfo,
} from '@/types/trust-scoring';

// ─────────────────────────────────────────────────────────────────────────────
// Query Keys
// ─────────────────────────────────────────────────────────────────────────────

export const trustScoringKeys = {
  all: ['trust-scoring'] as const,
  stats: () => [...trustScoringKeys.all, 'stats'] as const,
  author: (authorId: string) => [...trustScoringKeys.all, 'author', authorId] as const,
  content: (contentId: string) => [...trustScoringKeys.all, 'content', contentId] as const,
  campaign: (productId?: string) => [...trustScoringKeys.all, 'campaign', productId] as const,
  sentiment: (productId?: string) => [...trustScoringKeys.all, 'sentiment', productId] as const,
};

// ─────────────────────────────────────────────────────────────────────────────
// Statistics Query
// ─────────────────────────────────────────────────────────────────────────────

export function useTrustScoringStats() {
  return useQuery({
    queryKey: trustScoringKeys.stats(),
    queryFn: () => trustScoringApi.getStats(),
    staleTime: 60 * 1000, // 1 minute
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Author Scoring
// ─────────────────────────────────────────────────────────────────────────────

export function useScoreAuthor() {
  const toast = useToast();

  return useMutation({
    mutationFn: (data: AuthorScoreRequest) => trustScoringApi.scoreAuthor(data),
    onError: (error: Error) => {
      toast.error({
        title: 'Scoring failed',
        message: error.message || 'Failed to score author',
      });
    },
  });
}

export function useScoreAuthorsBatch() {
  const toast = useToast();

  return useMutation({
    mutationFn: (data: BatchAuthorScoreRequest) => trustScoringApi.scoreAuthorsBatch(data),
    onError: (error: Error) => {
      toast.error({
        title: 'Batch scoring failed',
        message: error.message || 'Failed to score authors',
      });
    },
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Content Analysis
// ─────────────────────────────────────────────────────────────────────────────

export function useAnalyzeContent() {
  const toast = useToast();

  return useMutation({
    mutationFn: (data: ContentAnalysisRequest) => trustScoringApi.analyzeContent(data),
    onError: (error: Error) => {
      toast.error({
        title: 'Analysis failed',
        message: error.message || 'Failed to analyze content',
      });
    },
  });
}

export function useAnalyzeContentBatch() {
  const toast = useToast();

  return useMutation({
    mutationFn: (data: BatchContentAnalysisRequest) => trustScoringApi.analyzeContentBatch(data),
    onError: (error: Error) => {
      toast.error({
        title: 'Batch analysis failed',
        message: error.message || 'Failed to analyze content',
      });
    },
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Campaign Detection
// ─────────────────────────────────────────────────────────────────────────────

export function useDetectCampaign() {
  const toast = useToast();

  return useMutation({
    mutationFn: (data: CampaignDetectionRequest) => trustScoringApi.detectCampaign(data),
    onSuccess: (result) => {
      if (result.is_campaign_detected) {
        toast.warning({
          title: 'Campaign Detected',
          message: `Coordinated activity detected with ${Math.round(result.campaign_confidence * 100)}% confidence`,
        });
      }
    },
    onError: (error: Error) => {
      toast.error({
        title: 'Detection failed',
        message: error.message || 'Failed to detect campaign',
      });
    },
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Weighted Sentiment
// ─────────────────────────────────────────────────────────────────────────────

export function useWeightedSentiment() {
  const toast = useToast();

  return useMutation({
    mutationFn: (data: WeightedSentimentRequest) => trustScoringApi.calculateWeightedSentiment(data),
    onError: (error: Error) => {
      toast.error({
        title: 'Calculation failed',
        message: error.message || 'Failed to calculate weighted sentiment',
      });
    },
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Quick Checks
// ─────────────────────────────────────────────────────────────────────────────

export function useQuickSpamCheck() {
  return useMutation({
    mutationFn: (data: QuickSpamCheckRequest) => trustScoringApi.checkSpam(data),
  });
}

export function useQuickTrustCheck() {
  return useMutation({
    mutationFn: (data: QuickTrustCheckRequest) => trustScoringApi.checkTrust(data),
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Cache Management
// ─────────────────────────────────────────────────────────────────────────────

export function useClearTrustCache() {
  const queryClient = useQueryClient();
  const toast = useToast();

  return useMutation({
    mutationFn: () => trustScoringApi.clearCache(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: trustScoringKeys.all });
      toast.success({
        title: 'Cache cleared',
        message: 'Trust scoring cache has been cleared',
      });
    },
    onError: (error: Error) => {
      toast.error({
        title: 'Failed to clear cache',
        message: error.message,
      });
    },
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper Hooks
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Get trust level display information
 */
export function useTrustLevelInfo(level: TrustLevel): TrustLevelInfo {
  const levelMap: Record<TrustLevel, TrustLevelInfo> = {
    verified: {
      level: 'verified',
      label: 'Verified',
      color: 'text-blue-700',
      bgColor: 'bg-blue-100',
      description: 'Verified account with established credibility',
    },
    high: {
      level: 'high',
      label: 'High Trust',
      color: 'text-green-700',
      bgColor: 'bg-green-100',
      description: 'Established account with good history',
    },
    medium: {
      level: 'medium',
      label: 'Medium Trust',
      color: 'text-yellow-700',
      bgColor: 'bg-yellow-100',
      description: 'Normal account, standard weighting',
    },
    low: {
      level: 'low',
      label: 'Low Trust',
      color: 'text-orange-700',
      bgColor: 'bg-orange-100',
      description: 'New or suspicious account, reduced weight',
    },
    untrusted: {
      level: 'untrusted',
      label: 'Untrusted',
      color: 'text-red-700',
      bgColor: 'bg-red-100',
      description: 'Likely bot or spam account',
    },
    blocked: {
      level: 'blocked',
      label: 'Blocked',
      color: 'text-gray-700',
      bgColor: 'bg-gray-100',
      description: 'Known bad actor, excluded from analysis',
    },
  };

  return levelMap[level] || levelMap.medium;
}

/**
 * Get risk flag display information
 */
export function useRiskFlagInfo(flag: RiskFlag): RiskFlagInfo {
  const flagMap: Record<RiskFlag, RiskFlagInfo> = {
    new_account: {
      flag: 'new_account',
      label: 'New Account',
      severity: 'low',
      description: 'Account is less than 30 days old',
    },
    low_followers: {
      flag: 'low_followers',
      label: 'Low Followers',
      severity: 'low',
      description: 'Account has very few followers',
    },
    high_post_frequency: {
      flag: 'high_post_frequency',
      label: 'High Post Frequency',
      severity: 'medium',
      description: 'Posting unusually frequently',
    },
    repetitive_content: {
      flag: 'repetitive_content',
      label: 'Repetitive Content',
      severity: 'medium',
      description: 'Similar content posted multiple times',
    },
    coordinated_timing: {
      flag: 'coordinated_timing',
      label: 'Coordinated Timing',
      severity: 'high',
      description: 'Posts synchronized with other accounts',
    },
    suspicious_engagement: {
      flag: 'suspicious_engagement',
      label: 'Suspicious Engagement',
      severity: 'medium',
      description: 'Engagement patterns appear artificial',
    },
    keyword_stuffing: {
      flag: 'keyword_stuffing',
      label: 'Keyword Stuffing',
      severity: 'medium',
      description: 'Excessive use of hashtags or keywords',
    },
    link_spam: {
      flag: 'link_spam',
      label: 'Link Spam',
      severity: 'medium',
      description: 'Contains excessive promotional links',
    },
    copy_paste: {
      flag: 'copy_paste',
      label: 'Copy/Paste',
      severity: 'high',
      description: 'Exact duplicate of other content',
    },
    sentiment_extreme: {
      flag: 'sentiment_extreme',
      label: 'Extreme Sentiment',
      severity: 'low',
      description: 'Consistently extreme positive or negative',
    },
    bot_pattern: {
      flag: 'bot_pattern',
      label: 'Bot Pattern',
      severity: 'high',
      description: 'Behavior matches known bot patterns',
    },
    fake_engagement: {
      flag: 'fake_engagement',
      label: 'Fake Engagement',
      severity: 'high',
      description: 'Engagement appears to be artificially inflated',
    },
  };

  return flagMap[flag] || {
    flag,
    label: flag.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    severity: 'medium' as const,
    description: 'Unknown risk flag',
  };
}

/**
 * Calculate sentiment shift percentage
 */
export function useSentimentShift(raw: number, adjusted: number): {
  shift: number;
  shiftPercent: number;
  direction: 'up' | 'down' | 'neutral';
  isSignificant: boolean;
} {
  const shift = adjusted - raw;
  const shiftPercent = raw !== 0 ? (shift / Math.abs(raw)) * 100 : 0;
  
  let direction: 'up' | 'down' | 'neutral' = 'neutral';
  if (shift > 0.02) direction = 'up';
  else if (shift < -0.02) direction = 'down';
  
  const isSignificant = Math.abs(shift) >= 0.05;
  
  return {
    shift: Math.round(shift * 1000) / 1000,
    shiftPercent: Math.round(shiftPercent),
    direction,
    isSignificant,
  };
}

/**
 * Get color for trust score
 */
export function getTrustScoreColor(score: number): string {
  if (score >= 0.7) return 'text-green-600';
  if (score >= 0.4) return 'text-yellow-600';
  if (score >= 0.2) return 'text-orange-600';
  return 'text-red-600';
}

/**
 * Get background color for trust score
 */
export function getTrustScoreBgColor(score: number): string {
  if (score >= 0.7) return 'bg-green-100';
  if (score >= 0.4) return 'bg-yellow-100';
  if (score >= 0.2) return 'bg-orange-100';
  return 'bg-red-100';
}

/**
 * Format trust score as percentage
 */
export function formatTrustScore(score: number): string {
  if (!Number.isFinite(score)) return '0%';
  const clamped = Math.max(0, Math.min(1, score));
  return `${Math.round(clamped * 100)}%`;
}



