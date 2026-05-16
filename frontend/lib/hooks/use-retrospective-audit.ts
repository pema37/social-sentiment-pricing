'use client';

/**
 * Retrospective Audit Hooks
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { retrospectiveAuditApi } from '@/lib/api/retrospective-audit';
import type { AuditRequest } from '@/types/retrospective-audit';

export const auditKeys = {
  all: ['retrospective-audit'] as const,
  latest: (days?: number) => [...auditKeys.all, 'latest', days] as const,
};

/** Fetch the latest audit (generates on the fly) */
export function useLatestAudit(lookbackDays: number = 90) {
  return useQuery({
    queryKey: auditKeys.latest(lookbackDays),
    queryFn: () => retrospectiveAuditApi.getLatest(lookbackDays),
    staleTime: 5 * 60 * 1000, // 5 min — audit data doesn't change rapidly
    refetchOnMount: true,
  });
}

/** Generate a custom audit (mutation) */
export function useGenerateAudit() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: AuditRequest) => retrospectiveAuditApi.generate(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: auditKeys.all });
    },
  });
}

/** Refresh audit data */
export function useRefreshAudit() {
  const queryClient = useQueryClient();
  return {
    refresh: () => queryClient.invalidateQueries({ queryKey: auditKeys.all }),
  };
}



