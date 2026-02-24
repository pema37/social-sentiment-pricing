// frontend/components/features/intelligence/OutcomeDashboard.tsx
'use client';

import { Card, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import {
  ArrowRight,
  DollarSign,
  TrendingUp,
  TrendingDown,
  CheckCircle,
  XCircle,
  MinusCircle,
  HelpCircle,
  Clock,
} from 'lucide-react';
import { useOutcomeCards, useAccuracyStats } from '@/lib/hooks/use-outcomes';
import type { OutcomeCardData, OutcomeLabel, MerchantDecision } from '@/types/outcome';

// ── Helpers ──

const labelConfig: Record<OutcomeLabel, { variant: 'success' | 'danger' | 'default' | 'warning'; icon: typeof CheckCircle; text: string }> = {
  positive: { variant: 'success', icon: CheckCircle, text: 'Positive' },
  negative: { variant: 'danger', icon: XCircle, text: 'Negative' },
  neutral: { variant: 'default', icon: MinusCircle, text: 'Neutral' },
  inconclusive: { variant: 'warning', icon: HelpCircle, text: 'Inconclusive' },
};

const decisionLabel: Record<MerchantDecision, string> = {
  accepted: 'Accepted',
  modified: 'Modified',
  rejected: 'Rejected',
  auto_applied: 'Auto-applied',
  expired: 'Expired',
  pending: 'Pending',
};

function formatCurrency(val: number): string {
  return `$${val.toFixed(2)}`;
}

function formatLiftBadge(lift: number | null) {
  if (lift === null) return <span className="text-xs text-gray-400">—</span>;
  const pct = (lift * 100).toFixed(1);
  if (lift >= 0) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs font-medium text-green-700">
        <TrendingUp className="w-3 h-3" />+{pct}%
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-0.5 text-xs font-medium text-red-700">
      <TrendingDown className="w-3 h-3" />{pct}%
    </span>
  );
}

// ── Accuracy Summary Strip ──

function AccuracySummary({ days }: { days: number }) {
  const { data: stats, isLoading } = useAccuracyStats(days);

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-16 bg-gray-100 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (!stats) return null;

  const summaryItems = [
    {
      label: 'Success Rate',
      value: stats.overall_success_rate,
      icon: CheckCircle,
      color: 'text-green-600',
      bg: 'bg-green-50',
    },
    {
      label: 'Total Outcomes',
      value: String(stats.total_outcomes),
      icon: DollarSign,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
    },
    {
      label: 'Revenue Impact',
      value: stats.total_revenue_impact,
      icon: TrendingUp,
      color: 'text-purple-600',
      bg: 'bg-purple-50',
    },
    {
      label: 'Avg Score',
      value: stats.avg_outcome_score,
      icon: TrendingUp,
      color: 'text-amber-600',
      bg: 'bg-amber-50',
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
      {summaryItems.map((item) => (
        <div key={item.label} className="flex items-center gap-3 bg-gray-50 rounded-lg p-3">
          <div className={`p-2 rounded-lg ${item.bg}`}>
            <item.icon className={`w-4 h-4 ${item.color}`} />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900">{item.value}</p>
            <p className="text-xs text-gray-500">{item.label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Single Outcome Row ──

function OutcomeRow({ outcome }: { outcome: OutcomeCardData }) {
  const config = labelConfig[outcome.outcomeLabel];
  const LabelIcon = config.icon;

  // Best available lift
  const bestWindow = outcome.measurementWindows
    .filter((w) => w.measured && w.lift !== null)
    .sort((a, b) => {
      const order = { '30d': 3, '14d': 2, '7d': 1 };
      return (order[b.window] ?? 0) - (order[a.window] ?? 0);
    })[0];

  return (
    <div className="flex items-center gap-4 py-3 px-1 border-b border-gray-50 last:border-0 hover:bg-gray-50 rounded-lg transition-colors">
      {/* Outcome label */}
      <div className="w-24 shrink-0">
        <Badge variant={config.variant}>
          <LabelIcon className="w-3 h-3 mr-1 inline" />
          {config.text}
        </Badge>
      </div>

      {/* Price change arrow */}
      <div className="flex items-center gap-1.5 w-44 shrink-0">
        <span className="text-sm text-gray-700 font-mono">
          {formatCurrency(outcome.priceChange.from)}
        </span>
        <ArrowRight className="w-3.5 h-3.5 text-gray-400" />
        <span className="text-sm font-semibold text-gray-900 font-mono">
          {formatCurrency(outcome.priceChange.to)}
        </span>
        <span className={`text-xs ${outcome.priceChange.percent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {outcome.priceChange.percent >= 0 ? '+' : ''}{outcome.priceChange.percent.toFixed(1)}%
        </span>
      </div>

      {/* Merchant decision */}
      <div className="w-24 shrink-0">
        <span className="text-xs text-gray-500">
          {decisionLabel[outcome.merchantDecision]}
        </span>
      </div>

      {/* Confidence */}
      <div className="w-20 shrink-0 text-right">
        <span className="text-xs text-gray-600">
          {(outcome.confidence * 100).toFixed(0)}% conf
        </span>
      </div>

      {/* Revenue lift */}
      <div className="w-20 shrink-0 text-right">
        {bestWindow ? (
          <div>
            {formatLiftBadge(bestWindow.lift)}
            <span className="text-[10px] text-gray-400 ml-1">{bestWindow.window}</span>
          </div>
        ) : (
          <span className="text-xs text-gray-400 flex items-center justify-end gap-1">
            <Clock className="w-3 h-3" /> Measuring
          </span>
        )}
      </div>

      {/* Measurement windows */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1">
          {outcome.measurementWindows.map((w) => (
            <div
              key={w.window}
              className={`h-1.5 flex-1 rounded-full ${
                w.measured
                  ? w.lift !== null && w.lift >= 0
                    ? 'bg-green-400'
                    : w.lift !== null
                    ? 'bg-red-400'
                    : 'bg-gray-300'
                  : 'bg-gray-100'
              }`}
              title={`${w.window}: ${w.measured ? (w.lift !== null ? `${(w.lift * 100).toFixed(1)}% lift` : 'Measured') : 'Pending'}`}
            />
          ))}
        </div>
        <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
          <span>7d</span>
          <span>14d</span>
          <span>30d</span>
        </div>
      </div>
    </div>
  );
}

// ── Main Component ──

interface OutcomeDashboardProps {
  days?: number;
}

export function OutcomeDashboard({ days = 30 }: OutcomeDashboardProps) {
  const { data: outcomes, isLoading } = useOutcomeCards({ days, limit: 20 });

  return (
    <Card>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-gray-400" />
          <CardTitle>Outcome Tracking</CardTitle>
        </div>
        {outcomes && outcomes.length > 0 && (
          <span className="text-xs text-gray-400">{outcomes.length} recent outcomes</span>
        )}
      </div>
      <p className="text-sm text-gray-500 mb-4">
        Recommendation → price change → revenue impact. Closing the feedback loop.
      </p>

      {/* Accuracy summary strip */}
      <AccuracySummary days={days} />

      {/* Outcome list */}
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-14 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : !outcomes || outcomes.length === 0 ? (
        <div className="text-center py-8 text-sm text-gray-400">
          <DollarSign className="w-8 h-8 mx-auto mb-2 text-gray-300" />
          No measured outcomes yet. Outcomes appear after recommendations are accepted and measured at 7/14/30 day windows.
        </div>
      ) : (
        <div>
          {/* Column headers */}
          <div className="flex items-center gap-4 py-2 px-1 text-[10px] uppercase tracking-wide text-gray-400 font-medium border-b border-gray-100">
            <span className="w-24 shrink-0">Result</span>
            <span className="w-44 shrink-0">Price Change</span>
            <span className="w-24 shrink-0">Decision</span>
            <span className="w-20 shrink-0 text-right">Confidence</span>
            <span className="w-20 shrink-0 text-right">Lift</span>
            <span className="flex-1">Measurement</span>
          </div>

          {outcomes.map((outcome) => (
            <OutcomeRow key={outcome.id} outcome={outcome} />
          ))}
        </div>
      )}
    </Card>
  );
}



