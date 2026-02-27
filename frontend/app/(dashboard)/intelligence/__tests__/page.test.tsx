import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React, { type ReactNode } from 'react';

interface HP { health?: { status?: string }; isLoading?: boolean }
interface EP { experiments?: unknown[]; isLoading?: boolean }
interface CP { reports?: unknown[]; isLoading?: boolean }
interface DP { alerts?: unknown[]; isLoading?: boolean }
interface TP { categories?: unknown[]; isLoading?: boolean }
interface OP { days?: number }
interface SHP { title: string; description: string; action: ReactNode }
interface BP { children: ReactNode; onClick?: () => void; className?: string }
interface IP { className?: string }

vi.mock('@/components/features/intelligence', () => ({
  IEHealthBanner: function M(p: HP) { return <div data-testid="ie-health-banner">{p.health?.status ?? 'no-health'}</div>; },
  ExperimentStatusCard: function M(p: EP) { return <div data-testid="experiment-status-card">{p.experiments?.length ?? 0} experiments</div>; },
  CalibrationChart: function M(p: CP) { return <div data-testid="calibration-chart">{p.reports?.length ?? 0} reports</div>; },
  DriftAlertsList: function M(p: DP) { return <div data-testid="drift-alerts-list">{p.alerts?.length ?? 0} alerts</div>; },
  CategoryPerformanceTable: function M(p: TP) { return <div data-testid="category-performance-table">{p.categories?.length ?? 0} categories</div>; },
  OutcomeDashboard: function M(p: OP) { return <div data-testid="outcome-dashboard">days={p.days ?? 30}</div>; },
}));

vi.mock('@/components/ui', () => ({
  SectionHeader: function M({ title, description, action }: SHP) { return <div data-testid="section-header"><h1>{title}</h1><p>{description}</p><div>{action}</div></div>; },
}));

vi.mock('@/components/ui/Button', () => ({
  Button: function M({ children, onClick, className }: BP) { return <button onClick={onClick} className={className}>{children}</button>; },
}));

vi.mock('lucide-react', () => ({
  RefreshCw: function M(p: IP) { return <span data-testid="icon-refresh" className={p.className}>R</span>; },
  Brain: function M(p: IP) { return <span data-testid="icon-brain" className={p.className}>B</span>; },
}));

vi.mock('@/lib/hooks/use-intelligence', () => ({
  useIEDashboard: vi.fn().mockReturnValue({
    data: {
      health: { status: 'healthy', scoring_engine_healthy: true, experiment_manager_healthy: true, calibrator_healthy: true, context_injector_healthy: true, active_experiments: 3, converged_categories: 1, total_categories: 5, drift_alerts_active: 2, pipeline_version: 'ie-v1.0' },
      top_categories: [{ category_id: 'cat-1', category_name: 'Electronics' }],
      active_drift_alerts: [{ alert_id: 'drift-1', severity: 'critical' }],
      recent_calibration: null,
    },
    isLoading: false, isFetching: false,
  }),
  useExperiments: vi.fn().mockReturnValue({ data: [{ category_id: 'cat-1' }], isLoading: false }),
  useCalibration: vi.fn().mockReturnValue({ data: [{ category_id: 'cat-1' }], isLoading: false }),
  useDriftAlerts: vi.fn().mockReturnValue({ data: [{ alert_id: 'drift-1' }], isLoading: false }),
  useCategoryPerformance: vi.fn().mockReturnValue({ data: [{ category_id: 'cat-1' }], isLoading: false }),
  intelligenceKeys: {
    all: ['intelligence'],
    dashboard: (n: number) => ['intelligence', 'dashboard', n],
    health: () => ['intelligence', 'health'],
    experiments: () => ['intelligence', 'experiments', 'all'],
    calibration: () => ['intelligence', 'calibration', 'global'],
    driftAlerts: () => ['intelligence', 'drift-alerts', 'all'],
    categories: () => ['intelligence', 'categories', undefined],
    category: (id: string) => ['intelligence', 'category', id],
  },
}));

import IntelligencePage from '@/app/(dashboard)/intelligence/page';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return function W({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe('Intelligence Dashboard Page', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders all 6 components', () => {
    render(<IntelligencePage />, { wrapper: createWrapper() });
    expect(screen.getByTestId('ie-health-banner')).not.toBeNull();
    expect(screen.getByTestId('experiment-status-card')).not.toBeNull();
    expect(screen.getByTestId('calibration-chart')).not.toBeNull();
    expect(screen.getByTestId('drift-alerts-list')).not.toBeNull();
    expect(screen.getByTestId('category-performance-table')).not.toBeNull();
    expect(screen.getByTestId('outcome-dashboard')).not.toBeNull();
  });

  it('renders page title', () => {
    render(<IntelligencePage />, { wrapper: createWrapper() });
    expect((document.body.textContent ?? '').toLowerCase()).toContain('intelligence');
  });

  it('passes data to children', () => {
    render(<IntelligencePage />, { wrapper: createWrapper() });
    expect(screen.getByTestId('ie-health-banner').textContent).toContain('healthy');
    expect(screen.getByTestId('experiment-status-card').textContent).toContain('1 experiments');
    expect(screen.getByTestId('calibration-chart').textContent).toContain('1 reports');
    expect(screen.getByTestId('drift-alerts-list').textContent).toContain('1 alerts');
    expect(screen.getByTestId('category-performance-table').textContent).toContain('1 categories');
  });

  it('has time range options', () => {
    render(<IntelligencePage />, { wrapper: createWrapper() });
    const t = document.body.textContent ?? '';
    expect(t).toContain('30 days');
    expect(t).toContain('60 days');
    expect(t).toContain('90 days');
  });

  it('changes days on time range click', () => {
    render(<IntelligencePage />, { wrapper: createWrapper() });
    expect(screen.getByTestId('outcome-dashboard').textContent).toContain('days=30');
    fireEvent.click(screen.getByText(/60 days/));
    expect(screen.getByTestId('outcome-dashboard').textContent).toContain('days=60');
  });

  it('has clickable refresh', () => {
    render(<IntelligencePage />, { wrapper: createWrapper() });
    const btn = screen.getByTestId('icon-refresh').closest('button');
    expect(btn).not.toBeNull();
    fireEvent.click(btn!);
  });
});



