// frontend/lib/api/__tests__/intelligence.test.ts
//
// Tests the intelligenceApi object — verifies correct URLs + params.
// Mocks the shared `api` client instead of MSW (avoids XMLHttpRequest patch conflicts).

import { describe, it, expect, vi, beforeEach } from 'vitest';

// ── Mock the shared HTTP client ──

const mockGet = vi.fn().mockResolvedValue({});

vi.mock('@/lib/api/client', () => ({
  api: {
    get: (...args: unknown[]) => mockGet(...args),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import { intelligenceApi } from '@/lib/api/intelligence';

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

describe('intelligenceApi', () => {
  beforeEach(() => {
    mockGet.mockClear();
    mockGet.mockResolvedValue({});
  });

  // ── dashboard ──

  describe('dashboard()', () => {
    it('calls /intelligence/dashboard with default top_n=10', async () => {
      await intelligenceApi.dashboard();
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/dashboard', { top_n: 10 });
    });

    it('passes custom top_n', async () => {
      await intelligenceApi.dashboard(20);
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/dashboard', { top_n: 20 });
    });
  });

  // ── health ──

  describe('health()', () => {
    it('calls /intelligence/health', async () => {
      await intelligenceApi.health();
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/health');
    });
  });

  // ── experiments ──

  describe('experiments()', () => {
    it('calls /intelligence/experiments with no params', async () => {
      await intelligenceApi.experiments();
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/experiments', {});
    });

    it('passes category_id when provided', async () => {
      await intelligenceApi.experiments('cat-1');
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/experiments', { category_id: 'cat-1' });
    });
  });

  // ── experiment (single) ──

  describe('experiment()', () => {
    it('calls /intelligence/experiments/:categoryId', async () => {
      await intelligenceApi.experiment('cat-1');
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/experiments/cat-1');
    });
  });

  // ── calibration ──

  describe('calibration()', () => {
    it('calls /intelligence/calibration with no params', async () => {
      await intelligenceApi.calibration();
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/calibration', {});
    });

    it('passes category_id when provided', async () => {
      await intelligenceApi.calibration('cat-1');
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/calibration', { category_id: 'cat-1' });
    });
  });

  // ── driftAlerts ──

  describe('driftAlerts()', () => {
    it('calls /intelligence/drift-alerts with no params', async () => {
      await intelligenceApi.driftAlerts();
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/drift-alerts', {});
    });

    it('passes severity filter', async () => {
      await intelligenceApi.driftAlerts({ severity: 'critical' });
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/drift-alerts', { severity: 'critical' });
    });

    it('passes active_only filter', async () => {
      await intelligenceApi.driftAlerts({ severity: 'warning', active_only: true });
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/drift-alerts', {
        severity: 'warning',
        active_only: true,
      });
    });
  });

  // ── categories ──

  describe('categories()', () => {
    it('calls /intelligence/categories with no params', async () => {
      await intelligenceApi.categories();
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/categories', {});
    });

    it('passes min_recommendations', async () => {
      await intelligenceApi.categories({ min_recommendations: 10 });
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/categories', { min_recommendations: 10 });
    });

    it('passes sort_by', async () => {
      await intelligenceApi.categories({ sort_by: 'acceptance_rate' });
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/categories', { sort_by: 'acceptance_rate' });
    });
  });

  // ── category (single) ──

  describe('category()', () => {
    it('calls /intelligence/categories/:categoryId', async () => {
      await intelligenceApi.category('cat-1');
      expect(mockGet).toHaveBeenCalledWith('/api/v1/intelligence/categories/cat-1');
    });
  });
});



