// frontend/components/features/intelligence/__tests__/DriftAlertsList.test.tsx

import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { DriftAlertsList } from '@/components/features/intelligence/DriftAlertsList';
import type { DriftAlert } from '@/types/intelligence';

const alerts: DriftAlert[] = [
  {
    alert_id: 'drift-3',
    category_id: 'cat-3',
    drift_type: 'acceptance_change',
    severity: 'info',
    metric_name: 'avg_confidence',
    current_value: 0.62,
    threshold: 0.6,
    message: 'Minor confidence shift detected',
    detected_at: '2026-02-20T08:00:00Z',
    requires_action: false,
  },
  {
    alert_id: 'drift-1',
    category_id: 'cat-1',
    drift_type: 'correlation_drop',
    severity: 'critical',
    metric_name: 'acceptance_rate',
    current_value: 0.3,
    threshold: 0.5,
    message: 'Acceptance rate dropped below threshold',
    detected_at: '2026-02-20T12:00:00Z',
    requires_action: true,
  },
  {
    alert_id: 'drift-2',
    category_id: 'cat-2',
    drift_type: 'distribution_shift',
    severity: 'warning',
    metric_name: 'confidence_spread',
    current_value: 0.8,
    threshold: 0.6,
    message: 'Confidence distribution shifted',
    detected_at: '2026-02-20T10:00:00Z',
    requires_action: false,
  },
];

describe('DriftAlertsList', () => {
  it('renders all alert messages', () => {
    render(<DriftAlertsList alerts={alerts} />);
    const text = document.body.textContent ?? '';
    expect(text).toContain('Acceptance rate dropped');
    expect(text).toContain('Confidence distribution shifted');
    expect(text).toContain('Minor confidence shift');
  });

  it('applies severity styling (red for critical)', () => {
    const { container } = render(<DriftAlertsList alerts={alerts} />);
    expect(container.querySelectorAll('[class*="red"]').length).toBeGreaterThan(0);
  });

  it('applies severity styling (yellow/amber for warning)', () => {
    const { container } = render(<DriftAlertsList alerts={alerts} />);
    expect(
      container.querySelectorAll('[class*="yellow"], [class*="amber"]').length,
    ).toBeGreaterThan(0);
  });

  it('displays drift type labels', () => {
    render(<DriftAlertsList alerts={alerts} />);
    const text = (document.body.textContent ?? '').toLowerCase();
    expect(text).toMatch(/correlation/);
    expect(text).toMatch(/distribution/);
  });

  it('shows action required flag', () => {
    render(<DriftAlertsList alerts={alerts} />);
    const text = (document.body.textContent ?? '').toLowerCase();
    expect(text).toMatch(/action/);
  });

  it('renders empty state', () => {
    render(<DriftAlertsList alerts={[]} />);
    const text = (document.body.textContent ?? '').toLowerCase();
    expect(text).toMatch(/no alert|no drift|all clear/);
  });

  it('shows loading skeleton', () => {
    const { container } = render(<DriftAlertsList alerts={[]} isLoading />);
    expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });
});



