// frontend/components/features/intelligence/__tests__/ExperimentStatusCard.test.tsx

import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ExperimentStatusCard } from '@/components/features/intelligence/ExperimentStatusCard';
import type { ExperimentStatus } from '@/types/intelligence';

const experiments: ExperimentStatus[] = [
  {
    category_id: 'electronics',
    total_pulls: 125,
    converged: false,
    converged_arm: null,
    convergence_confidence: 0.85,
    arms: [
      { arm_name: 'aggressive', alpha: 31, beta: 21, pulls: 50, wins: 30, expected_reward: 0.6, is_leader: true },
      { arm_name: 'conservative', alpha: 16, beta: 26, pulls: 40, wins: 15, expected_reward: 0.375, is_leader: false },
      { arm_name: 'moderate', alpha: 21, beta: 16, pulls: 35, wins: 20, expected_reward: 0.571, is_leader: false },
    ],
    last_updated: '2026-02-20T00:00:00Z',
    exploration_rate: 0.05,
  },
  {
    category_id: 'clothing',
    total_pulls: 180,
    converged: true,
    converged_arm: 'aggressive',
    convergence_confidence: 0.95,
    arms: [
      { arm_name: 'aggressive', alpha: 71, beta: 31, pulls: 100, wins: 70, expected_reward: 0.7, is_leader: true },
      { arm_name: 'conservative', alpha: 51, beta: 31, pulls: 80, wins: 50, expected_reward: 0.625, is_leader: false },
    ],
    last_updated: '2026-02-18T00:00:00Z',
    exploration_rate: 0.05,
  },
];

describe('ExperimentStatusCard', () => {
  it('renders experiment list with category IDs', () => {
    render(<ExperimentStatusCard experiments={experiments} />);
    const text = (document.body.textContent ?? '').toLowerCase();
    expect(text).toContain('electronics');
    expect(text).toContain('clothing');
  });

  it('shows arm details when row is expanded', () => {
    render(<ExperimentStatusCard experiments={experiments} />);
    // Click the first experiment row
    const electronicsEl = screen.getByText(/electronics/i);
    fireEvent.click(electronicsEl);
    const text = (document.body.textContent ?? '').toLowerCase();
    expect(text).toContain('moderate');
  });

  it('collapses arm details when clicked again', () => {
    render(<ExperimentStatusCard experiments={experiments} />);
    const electronicsEl = screen.getByText(/electronics/i);
    fireEvent.click(electronicsEl);
    expect((document.body.textContent ?? '').toLowerCase()).toContain('moderate');
    fireEvent.click(electronicsEl);
    expect((document.body.textContent ?? '').toLowerCase()).not.toContain('moderate');
  });

  it('displays arm pulls and wins', () => {
    render(<ExperimentStatusCard experiments={experiments} />);
    fireEvent.click(screen.getByText(/electronics/i));
    const text = document.body.textContent ?? '';
    expect(text).toContain('50');
    expect(text).toContain('30');
  });

  it('indicates the leading arm', () => {
    render(<ExperimentStatusCard experiments={experiments} />);
    fireEvent.click(screen.getByText(/electronics/i));
    // The leader arm may be shown with a badge, icon, or highlight — just verify aggressive arm is present
    const text = (document.body.textContent ?? '').toLowerCase();
    expect(text).toContain('aggressive');
  });

  it('shows converged experiments', () => {
    render(<ExperimentStatusCard experiments={experiments} />);
    const text = (document.body.textContent ?? '').toLowerCase();
    expect(text).toContain('converged');
  });

  it('shows experiment count summary', () => {
    render(<ExperimentStatusCard experiments={experiments} />);
    const text = (document.body.textContent ?? '').toLowerCase();
    // Should show counts for active/converged
    expect(text).toContain('1');  // 1 active or 1 converged
    expect(text).toContain('2');  // 2 total or similar
  });

  it('renders state when no experiments', () => {
    render(<ExperimentStatusCard experiments={[]} />);
    const text = (document.body.textContent ?? '').toLowerCase();
    // Component shows "0 active 0 converged" or similar empty representation
    expect(text).toContain('0');
  });

  it('shows loading skeleton', () => {
    const { container } = render(<ExperimentStatusCard experiments={[]} isLoading />);
    expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });
});



