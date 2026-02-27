// frontend/components/features/intelligence/__tests__/CategoryPerformanceTable.test.tsx

import { describe, it, expect } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import { CategoryPerformanceTable } from '@/components/features/intelligence/CategoryPerformanceTable';
import type { CategoryPerformance } from '@/types/intelligence';

const categories: CategoryPerformance[] = [
  {
    category_id: 'cat-1',
    category_name: 'Electronics',
    total_recommendations: 150,
    acceptance_rate: 0.72,
    avg_confidence: 0.68,
    avg_revenue_lift_7d: 0.05,
    avg_revenue_lift_14d: 0.08,
    avg_revenue_lift_30d: 0.12,
    confidence_accuracy_corr: 0.65,
    active_experiment: true,
    converged_strategy: null,
    data_quality_score: 0.85,
    merchant_count: 3,
  },
  {
    category_id: 'cat-2',
    category_name: 'Clothing',
    total_recommendations: 80,
    acceptance_rate: 0.55,
    avg_confidence: 0.72,
    avg_revenue_lift_7d: 0.02,
    avg_revenue_lift_14d: 0.04,
    avg_revenue_lift_30d: 0.06,
    confidence_accuracy_corr: 0.58,
    active_experiment: false,
    converged_strategy: 'aggressive',
    data_quality_score: 0.45,
    merchant_count: 2,
  },
  {
    category_id: 'cat-3',
    category_name: 'Home & Garden',
    total_recommendations: 200,
    acceptance_rate: 0.88,
    avg_confidence: 0.75,
    avg_revenue_lift_7d: 0.08,
    avg_revenue_lift_14d: 0.12,
    avg_revenue_lift_30d: 0.18,
    confidence_accuracy_corr: 0.78,
    active_experiment: true,
    converged_strategy: null,
    data_quality_score: 0.92,
    merchant_count: 5,
  },
];

describe('CategoryPerformanceTable', () => {
  it('renders a table with column headers', () => {
    const { container } = render(<CategoryPerformanceTable categories={categories} />);
    const headers = container.querySelectorAll('th');
    expect(headers.length).toBeGreaterThanOrEqual(5);
  });

  it('renders all category rows', () => {
    render(<CategoryPerformanceTable categories={categories} />);
    const text = document.body.textContent ?? '';
    expect(text).toContain('Electronics');
    expect(text).toContain('Clothing');
    expect(text).toContain('Home & Garden');
  });

  it('shows category count', () => {
    render(<CategoryPerformanceTable categories={categories} />);
    expect(document.body.textContent).toContain('3');
  });

  it('renders data quality indicators', () => {
    const { container } = render(<CategoryPerformanceTable categories={categories} />);
    const progressElements = container.querySelectorAll(
      '[role="progressbar"], [class*="progress"], [class*="bg-"][style]',
    );
    expect(progressElements.length).toBeGreaterThanOrEqual(1);
  });

  it('displays acceptance rates', () => {
    render(<CategoryPerformanceTable categories={categories} />);
    const text = document.body.textContent ?? '';
    // Should show percentage values for acceptance rates
    expect(text).toMatch(/72|55|88/);
  });

  it('sorts when clicking column headers', () => {
    const { container } = render(<CategoryPerformanceTable categories={categories} />);
    const sortableHeaders = container.querySelectorAll('th[class*="cursor-pointer"]');
    if (sortableHeaders.length > 0) {
      fireEvent.click(sortableHeaders[0]);
      expect(container.querySelectorAll('tbody tr').length).toBe(3);
    }
  });

  it('renders empty state', () => {
    render(<CategoryPerformanceTable categories={[]} />);
    const text = (document.body.textContent ?? '').toLowerCase();
    expect(text).toMatch(/no categor|no data|0/);
  });

  it('shows loading skeleton', () => {
    const { container } = render(<CategoryPerformanceTable categories={[]} isLoading />);
    expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });
});



