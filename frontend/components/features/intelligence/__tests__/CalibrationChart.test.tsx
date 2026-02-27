// frontend/components/features/intelligence/__tests__/CalibrationChart.test.tsx

import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { CalibrationChart } from '@/components/features/intelligence/CalibrationChart';
import type { CalibrationReport } from '@/types/intelligence';

const reports: CalibrationReport[] = [
  {
    category_id: 'cat-1',
    sample_count: 120,
    pearson_r: 0.72,
    calibration_method: 'isotonic',
    confidence_bands: [
      { band: '0.5-0.6', predicted: 0.55, actual: 0.52, count: 35 },
      { band: '0.6-0.7', predicted: 0.65, actual: 0.58, count: 42 },
      { band: '0.7-0.8', predicted: 0.75, actual: 0.68, count: 28 },
      { band: '0.8-0.9', predicted: 0.85, actual: 0.70, count: 15 },
    ],
    is_reliable: true,
    overconfidence_score: 0.07,
    last_calibrated: '2026-02-20T00:00:00Z',
  },
];

const overconfidentReports: CalibrationReport[] = [
  {
    ...reports[0],
    overconfidence_score: 0.25,
    confidence_bands: [
      { band: '0.5-0.6', predicted: 0.55, actual: 0.38, count: 35 },
      { band: '0.6-0.7', predicted: 0.65, actual: 0.45, count: 42 },
      { band: '0.7-0.8', predicted: 0.75, actual: 0.52, count: 28 },
      { band: '0.8-0.9', predicted: 0.85, actual: 0.58, count: 15 },
    ],
  },
];

describe('CalibrationChart', () => {
  it('renders SVG chart element', () => {
    const { container } = render(<CalibrationChart reports={reports} />);
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
  });

  it('renders data visualization elements', () => {
    const { container } = render(<CalibrationChart reports={reports} />);
    const svg = container.querySelector('svg');
    // SVG should contain visual elements (circles, rects, paths, lines, etc.)
    const elements = svg?.querySelectorAll('circle, rect, path, line, g');
    expect((elements?.length ?? 0)).toBeGreaterThan(0);
  });

  it('shows Pearson r value', () => {
    render(<CalibrationChart reports={reports} />);
    expect(document.body.textContent).toContain('0.72');
  });

  it('shows overconfidence indicator when score is high', () => {
    render(<CalibrationChart reports={overconfidentReports} />);
    const text = (document.body.textContent ?? '').toLowerCase();
    expect(text).toMatch(/overconfiden|bias/);
  });

  it('displays stats (samples, method)', () => {
    render(<CalibrationChart reports={reports} />);
    const text = document.body.textContent ?? '';
    expect(text).toContain('120');
    expect(text.toLowerCase()).toContain('isotonic');
  });

  it('shows loading skeleton', () => {
    const { container } = render(<CalibrationChart reports={[]} isLoading />);
    expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });

  it('shows empty state', () => {
    render(<CalibrationChart reports={[]} />);
    const text = (document.body.textContent ?? '').toLowerCase();
    expect(text).toMatch(/no calibration|no data|insufficient/);
  });
});



