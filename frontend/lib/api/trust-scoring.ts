// frontend/lib/api/trust-scoring.ts

/**
 * Trust Scoring / Bot Detection API Client
 */

import { api } from './client';
import type {
  AuthorScoreRequest,
  AuthorScoreResponse,
  BatchAuthorScoreRequest,
  BatchAuthorScoreResponse,
  ContentAnalysisRequest,
  ContentAnalysisResponse,
  BatchContentAnalysisRequest,
  BatchContentAnalysisResponse,
  CampaignDetectionRequest,
  CampaignDetectionResponse,
  WeightedSentimentRequest,
  WeightedSentimentResponse,
  QuickSpamCheckRequest,
  QuickSpamCheckResponse,
  QuickTrustCheckRequest,
  QuickTrustCheckResponse,
  TrustScoringStats,
} from '@/types/trust-scoring';

const BASE_PATH = '/api/v1/trust';

export const trustScoringApi = {
  // ─────────────────────────────────────────────────────────────────────────
  // Author Scoring
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Score a single author's trustworthiness
   */
  scoreAuthor: (data: AuthorScoreRequest) =>
    api.post<AuthorScoreResponse>(`${BASE_PATH}/author/score`, data),

  /**
   * Score multiple authors in batch
   */
  scoreAuthorsBatch: (data: BatchAuthorScoreRequest) =>
    api.post<BatchAuthorScoreResponse>(`${BASE_PATH}/author/score/batch`, data),

  // ─────────────────────────────────────────────────────────────────────────
  // Content Analysis
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Analyze content for spam/quality
   */
  analyzeContent: (data: ContentAnalysisRequest) =>
    api.post<ContentAnalysisResponse>(`${BASE_PATH}/content/analyze`, data),

  /**
   * Analyze multiple content pieces in batch
   */
  analyzeContentBatch: (data: BatchContentAnalysisRequest) =>
    api.post<BatchContentAnalysisResponse>(`${BASE_PATH}/content/analyze/batch`, data),

  // ─────────────────────────────────────────────────────────────────────────
  // Campaign Detection
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Detect coordinated manipulation campaigns
   */
  detectCampaign: (data: CampaignDetectionRequest) =>
    api.post<CampaignDetectionResponse>(`${BASE_PATH}/campaign/detect`, data),

  // ─────────────────────────────────────────────────────────────────────────
  // Weighted Sentiment
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Calculate trust-adjusted sentiment
   */
  calculateWeightedSentiment: (data: WeightedSentimentRequest) =>
    api.post<WeightedSentimentResponse>(`${BASE_PATH}/sentiment/weighted`, data),

  // ─────────────────────────────────────────────────────────────────────────
  // Quick Checks
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Quick spam check for content
   */
  checkSpam: (data: QuickSpamCheckRequest) =>
    api.post<QuickSpamCheckResponse>(`${BASE_PATH}/check/spam`, data),

  /**
   * Quick trust check for an author
   */
  checkTrust: (data: QuickTrustCheckRequest) =>
    api.post<QuickTrustCheckResponse>(`${BASE_PATH}/check/trust`, data),

  // ─────────────────────────────────────────────────────────────────────────
  // Statistics & Management
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Get trust scoring service statistics
   */
  getStats: () =>
    api.get<TrustScoringStats>(`${BASE_PATH}/stats`),

  /**
   * Clear all caches
   */
  clearCache: () =>
    api.post<{ success: boolean; message: string }>(`${BASE_PATH}/cache/clear`),
};

export default trustScoringApi;



