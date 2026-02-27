import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React, { type ReactNode } from 'react';

// vi.hoisted runs BEFORE vi.mock hoisting — safe to reference in factories
const mocks = vi.hoisted(() => ({
  useOutcomeCards: vi.fn(),
  useAccuracyStats: vi.fn(),
}));

vi.mock('lucide-react', () => ({
  ArrowRight: function I() { return <span />; },
  DollarSign: function I() { return <span />; },
  TrendingUp: function I() { return <span />; },
  TrendingDown: function I() { return <span />; },
  CheckCircle: function I() { return <span />; },
  XCircle: function I() { return <span />; },
  MinusCircle: function I() { return <span />; },
  HelpCircle: function I() { return <span />; },
  Clock: function I() { return <span />; },
}));

vi.mock('@/lib/hooks/use-outcomes', () => ({
  useOutcomeCards: (...a: unknown[]) => mocks.useOutcomeCards(...a),
  useAccuracyStats: (...a: unknown[]) => mocks.useAccuracyStats(...a),
  useOutcomeDashboard: vi.fn().mockReturnValue({ accuracy: null, calibration: null, isLoading: false }),
  useOutcomes: vi.fn().mockReturnValue({ data: [], isLoading: false }),
  useConfidenceCalibration: vi.fn().mockReturnValue({ data: null, isLoading: false }),
  outcomeKeys: { all: ['outcomes'] },
}));

import { OutcomeDashboard } from '@/components/features/intelligence/OutcomeDashboard';

function Wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

// Fixtures using exact OutcomeCardData interface (camelCase fields)
const accuracy = {
  total_outcomes: 85,
  success_count: 62,
  success_rate: 0.729,
  avg_revenue_lift: 0.087,
  revenue_impact: 12500,
};

const outcomes = [
  {
    id: 'out-1',
    productId: 'prod-1',
    outcomeLabel: 'positive' as const,
    outcomeScore: 0.85,
    priceChange: { from: 49.99, to: 54.99, percent: 10 },
    confidence: 0.78,
    confidenceBreakdown: { elasticity: 0.8, position: 0.7, urgency: null, dataQuality: 0.9 },
    merchantDecision: 'accepted' as const,
    measurementWindows: [
      { window: '7d', measured: true, lift: 0.05 },
      { window: '14d', measured: true, lift: 0.08 },
    ],
    measurementStatus: 'complete' as const,
    appliedAt: '2026-02-10T00:00:00Z',
    hasEvidence: true,
  },
  {
    id: 'out-2',
    productId: 'prod-2',
    outcomeLabel: 'positive' as const,
    outcomeScore: 0.72,
    priceChange: { from: 19.99, to: 14.99, percent: -25 },
    confidence: 0.65,
    confidenceBreakdown: { elasticity: 0.6, position: 0.7, urgency: null, dataQuality: 0.8 },
    merchantDecision: 'modified' as const,
    measurementWindows: [
      { window: '7d', measured: true, lift: 0.12 },
    ],
    measurementStatus: 'in_progress' as const,
    appliedAt: '2026-02-15T00:00:00Z',
    hasEvidence: true,
  },
  {
    id: 'out-3',
    productId: 'prod-3',
    outcomeLabel: 'negative' as const,
    outcomeScore: 0,
    priceChange: { from: 9.99, to: 12.99, percent: 30 },
    confidence: 0.55,
    confidenceBreakdown: { elasticity: null, position: null, urgency: null, dataQuality: 0.5 },
    merchantDecision: 'rejected' as const,
    measurementWindows: [],
    measurementStatus: 'pending' as const,
    appliedAt: '2026-02-18T00:00:00Z',
    hasEvidence: false,
  },
];

describe('OutcomeDashboard', () => {
  beforeEach(() => {
    mocks.useAccuracyStats.mockReturnValue({ data: accuracy, isLoading: false, isError: false });
    mocks.useOutcomeCards.mockReturnValue({ data: outcomes, isLoading: false, isError: false });
  });

  it('renders accuracy summary', () => {
    render(<OutcomeDashboard />, { wrapper: Wrapper });
    const t = document.body.textContent ?? '';
    expect(t).toContain('Success Rate');
    expect(t).toContain('Revenue Impact');
  });

  it('renders outcome cards', () => {
    render(<OutcomeDashboard />, { wrapper: Wrapper });
    const t = document.body.textContent ?? '';
    // Prices should be visible
    expect(t).toMatch(/49\.99|54\.99/);
    expect(t).toMatch(/19\.99|14\.99/);
  });

  it('displays merchant decisions', () => {
    render(<OutcomeDashboard />, { wrapper: Wrapper });
    const t = (document.body.textContent ?? '').toLowerCase();
    expect(t).toMatch(/accepted/);
    expect(t).toMatch(/modified/);
    expect(t).toMatch(/rejected/);
  });

  it('shows measurement data', () => {
    render(<OutcomeDashboard />, { wrapper: Wrapper });
    const t = document.body.textContent ?? '';
    expect(t).toMatch(/7d|14d|30d/);
  });

  it('shows loading state', () => {
    mocks.useAccuracyStats.mockReturnValue({ data: undefined, isLoading: true, isError: false });
    mocks.useOutcomeCards.mockReturnValue({ data: undefined, isLoading: true, isError: false });
    const { container } = render(<OutcomeDashboard />, { wrapper: Wrapper });
    expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });

  it('shows empty state', () => {
    mocks.useAccuracyStats.mockReturnValue({ data: { total_outcomes: 0, success_count: 0, success_rate: 0, revenue_impact: 0 }, isLoading: false, isError: false });
    mocks.useOutcomeCards.mockReturnValue({ data: [], isLoading: false, isError: false });
    render(<OutcomeDashboard />, { wrapper: Wrapper });
    expect((document.body.textContent ?? '').toLowerCase()).toMatch(/no.*outcome|no data|get started/);
  });
});



