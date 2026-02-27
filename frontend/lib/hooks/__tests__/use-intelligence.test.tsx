import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React, { type ReactNode } from 'react';

const mockApi = vi.hoisted(() => ({
  dashboard: vi.fn().mockResolvedValue({ health: { status: 'healthy' }, top_categories: [], active_drift_alerts: [], recent_calibration: null }),
  health: vi.fn().mockResolvedValue({ status: 'healthy' }),
  experiments: vi.fn().mockResolvedValue([{ category_id: 'cat-1' }]),
  experiment: vi.fn().mockResolvedValue({ category_id: 'cat-1' }),
  calibration: vi.fn().mockResolvedValue([{ category_id: 'cat-1', pearson_r: 0.72 }]),
  driftAlerts: vi.fn().mockResolvedValue([{ alert_id: 'drift-1' }]),
  categories: vi.fn().mockResolvedValue([{ category_id: 'cat-1' }]),
  category: vi.fn().mockResolvedValue({ category_id: 'cat-1' }),
}));

vi.mock('@/lib/api/intelligence', () => ({ intelligenceApi: mockApi }));

import {
  intelligenceKeys,
  useIEDashboard,
  useIEHealth,
  useExperiments,
  useCalibration,
  useDriftAlerts,
  useCategoryPerformance,
} from '@/lib/hooks/use-intelligence';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return function W({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe('intelligenceKeys', () => {
  it('dashboard key includes topN', () => {
    expect(intelligenceKeys.dashboard(10)).toEqual(['intelligence', 'dashboard', 10]);
    expect(intelligenceKeys.dashboard(20)).toEqual(['intelligence', 'dashboard', 20]);
  });
  it('health key', () => {
    expect(intelligenceKeys.health()).toEqual(['intelligence', 'health']);
  });
  it('experiments defaults to all', () => {
    expect(intelligenceKeys.experiments()).toEqual(['intelligence', 'experiments', 'all']);
  });
  it('experiments with category', () => {
    expect(intelligenceKeys.experiments('cat-1')).toEqual(['intelligence', 'experiments', 'cat-1']);
  });
  it('calibration defaults to global', () => {
    expect(intelligenceKeys.calibration()).toEqual(['intelligence', 'calibration', 'global']);
  });
  it('driftAlerts defaults to all', () => {
    expect(intelligenceKeys.driftAlerts()).toEqual(['intelligence', 'drift-alerts', 'all']);
  });
  it('categories with params', () => {
    const p = { min_recommendations: 5 };
    expect(intelligenceKeys.categories(p)).toEqual(['intelligence', 'categories', p]);
  });
  it('category key', () => {
    expect(intelligenceKeys.category('cat-1')).toEqual(['intelligence', 'category', 'cat-1']);
  });
});

describe('useIEDashboard', () => {
  beforeEach(() => vi.clearAllMocks());
  it('fetches with default topN=10', async () => {
    const { result } = renderHook(() => useIEDashboard(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.dashboard).toHaveBeenCalledWith(10);
  });
  it('passes custom topN', async () => {
    const { result } = renderHook(() => useIEDashboard(20), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.dashboard).toHaveBeenCalledWith(20);
  });
});

describe('useIEHealth', () => {
  beforeEach(() => vi.clearAllMocks());
  it('fetches health', async () => {
    const { result } = renderHook(() => useIEHealth(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe('healthy');
  });
});

describe('useExperiments', () => {
  beforeEach(() => vi.clearAllMocks());
  it('fetches all', async () => {
    const { result } = renderHook(() => useExperiments(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.experiments).toHaveBeenCalledWith(undefined);
  });
  it('passes categoryId', async () => {
    const { result } = renderHook(() => useExperiments('cat-1'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.experiments).toHaveBeenCalledWith('cat-1');
  });
});

describe('useCalibration', () => {
  beforeEach(() => vi.clearAllMocks());
  it('fetches all', async () => {
    const { result } = renderHook(() => useCalibration(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.calibration).toHaveBeenCalledWith(undefined);
  });
});

describe('useDriftAlerts', () => {
  beforeEach(() => vi.clearAllMocks());
  it('fetches all', async () => {
    const { result } = renderHook(() => useDriftAlerts(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.driftAlerts).toHaveBeenCalledWith({ severity: undefined, active_only: true });
  });
  it('passes severity', async () => {
    const { result } = renderHook(() => useDriftAlerts('critical'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.driftAlerts).toHaveBeenCalledWith({ severity: 'critical', active_only: true });
  });
});

describe('useCategoryPerformance', () => {
  beforeEach(() => vi.clearAllMocks());
  it('fetches all', async () => {
    const { result } = renderHook(() => useCategoryPerformance(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.categories).toHaveBeenCalledWith(undefined);
  });
  it('passes params', async () => {
    const p = { min_recommendations: 10 };
    const { result } = renderHook(() => useCategoryPerformance(p), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApi.categories).toHaveBeenCalledWith(p);
  });
});



