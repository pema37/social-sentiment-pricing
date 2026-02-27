// frontend/components/features/intelligence/__tests__/IEHealthBanner.test.tsx

import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { IEHealthBanner } from '@/components/features/intelligence/IEHealthBanner';
import type { IEHealthStatus } from '@/types/intelligence';

const healthy: IEHealthStatus = {
  status: 'healthy',
  scoring_engine_healthy: true,
  experiment_manager_healthy: true,
  calibrator_healthy: true,
  context_injector_healthy: true,
  active_experiments: 3,
  converged_categories: 1,
  total_categories: 5,
  drift_alerts_active: 2,
  pipeline_version: 'ie-v1.0',
  last_measurement_run: null,
  last_learning_cycle: null,
  last_bandit_update: null,
  last_calibration: null,
};

describe('IEHealthBanner', () => {
  it('renders healthy status', () => {
    render(<IEHealthBanner health={healthy} />);
    const text = (document.body.textContent ?? '').toLowerCase();
    expect(text).toContain('operational');
  });

  it('renders degraded status', () => {
    render(<IEHealthBanner health={{ ...healthy, status: 'degraded', calibrator_healthy: false }} />);
    const text = (document.body.textContent ?? '').toLowerCase();
    expect(text).toContain('degradation');
  });

  it('renders unhealthy status', () => {
    render(
      <IEHealthBanner
        health={{ ...healthy, status: 'unhealthy', scoring_engine_healthy: false, experiment_manager_healthy: false }}
      />,
    );
    const text = (document.body.textContent ?? '').toLowerCase();
    expect(text).toContain('unhealthy');
  });

  it('shows component health labels', () => {
    render(<IEHealthBanner health={healthy} />);
    const text = (document.body.textContent ?? '').toLowerCase();
    expect(text).toContain('scor');
    expect(text).toContain('experiment');
    expect(text).toContain('calibrat');
    expect(text).toContain('context');
  });

  it('has green indicators when all healthy', () => {
    const { container } = render(<IEHealthBanner health={healthy} />);
    expect(container.querySelectorAll('[class*="green"]').length).toBeGreaterThanOrEqual(4);
  });

  it('has red indicators for unhealthy components', () => {
    const { container } = render(
      <IEHealthBanner health={{ ...healthy, status: 'degraded', calibrator_healthy: false, context_injector_healthy: false }} />,
    );
    expect(container.querySelectorAll('[class*="red"]').length).toBeGreaterThanOrEqual(2);
  });

  it('displays experiment stats', () => {
    render(<IEHealthBanner health={healthy} />);
    const text = document.body.textContent ?? '';
    expect(text).toContain('3');
    expect(text).toContain('2');
  });

  it('shows loading skeleton', () => {
    const { container } = render(<IEHealthBanner health={undefined as unknown as IEHealthStatus} isLoading />);
    expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });
});




