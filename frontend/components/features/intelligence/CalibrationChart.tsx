// frontend/components/features/intelligence/CalibrationChart.tsx
'use client';

import { Card, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Target, AlertTriangle, CheckCircle } from 'lucide-react';
import type { CalibrationReport, CalibrationBand } from '@/types/intelligence';

interface CalibrationChartProps {
  reports: CalibrationReport[];
  isLoading?: boolean;
}

/**
 * SVG-based calibration chart.
 * X-axis: predicted confidence, Y-axis: actual accuracy.
 * Diagonal = perfect calibration.
 */
function CalibrationPlot({ bands }: { bands: CalibrationBand[] }) {
  const width = 320;
  const height = 240;
  const pad = { top: 16, right: 16, bottom: 32, left: 40 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const toX = (v: number) => pad.left + v * plotW;
  const toY = (v: number) => pad.top + (1 - v) * plotH;

  const sortedBands = [...bands].sort((a, b) => a.predicted - b.predicted);
  const dataPath = sortedBands
    .map((b, i) => `${i === 0 ? 'M' : 'L'} ${toX(b.predicted)} ${toY(b.actual)}`)
    .join(' ');

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full max-w-sm" aria-label="Calibration chart">
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={v}>
          <line
            x1={pad.left} y1={toY(v)} x2={width - pad.right} y2={toY(v)}
            stroke="#f3f4f6" strokeWidth={1}
          />
          <text x={pad.left - 6} y={toY(v) + 4} textAnchor="end" className="fill-gray-400" fontSize={10}>
            {(v * 100).toFixed(0)}%
          </text>
        </g>
      ))}
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <text key={`x-${v}`} x={toX(v)} y={height - 4} textAnchor="middle" className="fill-gray-400" fontSize={10}>
          {(v * 100).toFixed(0)}%
        </text>
      ))}

      {/* Axis labels */}
      <text x={width / 2} y={height - 0} textAnchor="middle" className="fill-gray-500" fontSize={10}>
        Predicted Confidence
      </text>
      <text
        x={12} y={height / 2}
        textAnchor="middle" className="fill-gray-500" fontSize={10}
        transform={`rotate(-90 12 ${height / 2})`}
      >
        Actual Accuracy
      </text>

      {/* Perfect calibration diagonal */}
      <line
        x1={toX(0)} y1={toY(0)} x2={toX(1)} y2={toY(1)}
        stroke="#d1d5db" strokeWidth={1.5} strokeDasharray="6 4"
      />
      <text x={toX(0.82)} y={toY(0.86)} className="fill-gray-400" fontSize={9}>
        Perfect
      </text>

      {/* Data line */}
      {sortedBands.length > 1 && (
        <path d={dataPath} fill="none" stroke="#3b82f6" strokeWidth={2} />
      )}

      {/* Data points */}
      {sortedBands.map((b) => (
        <g key={b.band}>
          <circle
            cx={toX(b.predicted)} cy={toY(b.actual)}
            r={Math.min(Math.max(Math.sqrt(b.count) * 1.5, 3), 10)}
            fill="#3b82f6" fillOpacity={0.7}
            stroke="#1d4ed8" strokeWidth={1}
          />
          {b.count >= 10 && (
            <text
              x={toX(b.predicted)} y={toY(b.actual) - 8}
              textAnchor="middle" className="fill-gray-600" fontSize={9}
            >
              {(b.actual * 100).toFixed(0)}%
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}

function PearsonBadge({ r }: { r: number | null | undefined }) {
  if (r == null) return <Badge variant="default">No data</Badge>;
  if (r >= 0.7) return <Badge variant="success">r = {r.toFixed(2)} (strong)</Badge>;
  if (r >= 0.4) return <Badge variant="warning">r = {r.toFixed(2)} (moderate)</Badge>;
  return <Badge variant="danger">r = {r.toFixed(2)} (weak)</Badge>;
}

function OverconfidenceIndicator({ score }: { score: number | null | undefined }) {
  if (score == null) return null;
  const abs = Math.abs(score);
  if (abs < 0.05) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-green-600">
        <CheckCircle className="w-3.5 h-3.5" />
        Well-calibrated
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1.5 text-xs text-amber-600">
      <AlertTriangle className="w-3.5 h-3.5" />
      {score > 0 ? 'Overconfident' : 'Underconfident'} by {(abs * 100).toFixed(1)}%
    </div>
  );
}

export function CalibrationChart({ reports, isLoading }: CalibrationChartProps) {
  if (isLoading) {
    return (
      <Card>
        <CardTitle>Confidence Calibration</CardTitle>
        <div className="mt-4 h-60 bg-gray-100 rounded-lg animate-pulse" />
      </Card>
    );
  }

  const report = reports?.[0];
  const bands = (report?.confidence_bands ?? []) as unknown as CalibrationBand[];

  return (
    <Card>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Target className="w-5 h-5 text-gray-400" />
          <CardTitle>Confidence Calibration</CardTitle>
        </div>
        {report && <PearsonBadge r={report.pearson_r} />}
      </div>
      <p className="text-sm text-gray-500 mb-4">
        Does predicted confidence match actual accuracy? Points near the diagonal = trustworthy scores.
      </p>

      {!report || report.sample_count === 0 ? (
        <div className="text-center py-8 text-sm text-gray-400">
          <Target className="w-8 h-8 mx-auto mb-2 text-gray-300" />
          Insufficient data. Calibration requires 30+ measured outcomes.
        </div>
      ) : (
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Chart */}
          <div className="flex-1 flex justify-center">
            <CalibrationPlot bands={bands} />
          </div>

          {/* Stats sidebar */}
          <div className="lg:w-48 space-y-4">
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Samples</p>
              <p className="text-lg font-semibold text-gray-900">{report.sample_count}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Reliability</p>
              <Badge variant={report.is_reliable ? 'success' : 'warning'}>
                {report.is_reliable ? 'Reliable' : 'Low sample'}
              </Badge>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Bias</p>
              <OverconfidenceIndicator score={report.overconfidence_score} />
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Method</p>
              <p className="text-sm text-gray-700">{report.calibration_method}</p>
            </div>

            {/* Band breakdown */}
            {bands.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Bands</p>
                <div className="space-y-1">
                  {bands.map((b) => (
                    <div key={b.band} className="flex items-center justify-between text-xs">
                      <span className="text-gray-500 font-mono">{b.band}</span>
                      <span className="text-gray-700">
                        {(b.actual * 100).toFixed(0)}%
                        <span className="text-gray-400 ml-1">({b.count})</span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}


