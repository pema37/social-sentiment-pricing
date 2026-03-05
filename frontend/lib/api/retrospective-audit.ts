/**
 * Retrospective Audit API
 */
import { api } from './client';
import type {
  AuditRequest,
  RetrospectiveAuditResponse,
} from '@/types/retrospective-audit';

export const retrospectiveAuditApi = {
  /** Generate a new retrospective loss audit */
  generate: (request: AuditRequest = {}) =>
    api.post<RetrospectiveAuditResponse>('/api/v1/audit/retrospective', request),

  /** Get latest audit (convenience — generates on the fly) */
  getLatest: (lookbackDays: number = 90) =>
    api.get<RetrospectiveAuditResponse>('/api/v1/audit/retrospective/latest', {
      lookback_days: lookbackDays,
    }),
};


