// frontend/components/features/intelligence/CategoryPerformanceTable.tsx
'use client';

import { useState, useMemo } from 'react';
import { Card, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { BarChart3, ArrowUpDown, FlaskConical, CheckCircle } from 'lucide-react';
import type { CategoryPerformance } from '@/types/intelligence';

interface CategoryPerformanceTableProps {
  categories: CategoryPerformance[];
  isLoading?: boolean;
}

type SortKey =
  | 'total_recommendations'
  | 'acceptance_rate'
  | 'avg_confidence'
  | 'avg_revenue_lift_7d'
  | 'data_quality_score';

function formatPct(val: number | null | undefined, decimals = 1): string {
  if (val === null || val === undefined) return '—';
  return `${(val * 100).toFixed(decimals)}%`;
}

function formatLift(val: number | null | undefined): string {
  if (val === null || val === undefined) return '—';
  const pct = (val * 100).toFixed(1);
  return val >= 0 ? `+${pct}%` : `${pct}%`;
}

function DataQualityBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${
            score >= 0.8 ? 'bg-green-500' : score >= 0.5 ? 'bg-amber-400' : 'bg-red-400'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-500">{pct}%</span>
    </div>
  );
}

export function CategoryPerformanceTable({ categories, isLoading }: CategoryPerformanceTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('total_recommendations');
  const [sortAsc, setSortAsc] = useState(false);

  const sorted = useMemo(() => {
    return [...categories].sort((a, b) => {
      const aVal = a[sortKey] ?? -Infinity;
      const bVal = b[sortKey] ?? -Infinity;
      return sortAsc ? (aVal > bVal ? 1 : -1) : (aVal < bVal ? 1 : -1);
    });
  }, [categories, sortKey, sortAsc]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  }

  const columns: { key: SortKey; label: string; className?: string }[] = [
    { key: 'total_recommendations', label: 'Recs', className: 'w-16 text-right' },
    { key: 'acceptance_rate', label: 'Accept Rate', className: 'w-24 text-right' },
    { key: 'avg_confidence', label: 'Avg Confidence', className: 'w-28 text-right' },
    { key: 'avg_revenue_lift_7d', label: '7d Lift', className: 'w-20 text-right' },
    { key: 'data_quality_score', label: 'Data Quality', className: 'w-28' },
  ];

  if (isLoading) {
    return (
      <Card>
        <CardTitle>Category Performance</CardTitle>
        <div className="mt-4 space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      </Card>
    );
  }

  return (
    <Card padding="none">
      <div className="p-6 pb-0">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-gray-400" />
            <CardTitle>Category Performance</CardTitle>
          </div>
          <span className="text-xs text-gray-400">{categories.length} categories</span>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          Per-category acceptance rates, revenue lift, and data quality
        </p>
      </div>

      {categories.length === 0 ? (
        <div className="text-center py-8 text-sm text-gray-400 px-6 pb-6">
          <BarChart3 className="w-8 h-8 mx-auto mb-2 text-gray-300" />
          No category data yet. Performance appears after 5+ recommendations per category.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-t border-b border-gray-100">
                <th className="text-left py-2.5 px-6 text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Category
                </th>
                {columns.map((col) => (
                  <th
                    key={col.key}
                    className={`py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide cursor-pointer hover:text-gray-700 select-none ${col.className ?? ''}`}
                    onClick={() => toggleSort(col.key)}
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.label}
                      <ArrowUpDown className={`w-3 h-3 ${sortKey === col.key ? 'text-gray-700' : 'text-gray-300'}`} />
                    </span>
                  </th>
                ))}
                <th className="py-2.5 px-3 text-xs font-medium text-gray-500 uppercase tracking-wide w-24">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((cat) => (
                <tr
                  key={cat.category_id}
                  className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                >
                  {/* Category name */}
                  <td className="py-3 px-6">
                    <span className="font-medium text-gray-900">
                      {cat.category_name || cat.category_id}
                    </span>
                    <span className="text-xs text-gray-400 ml-2">
                      {cat.merchant_count} merchant{cat.merchant_count !== 1 ? 's' : ''}
                    </span>
                  </td>

                  {/* Recommendations count */}
                  <td className="py-3 px-3 text-right text-gray-700 font-medium">
                    {cat.total_recommendations}
                  </td>

                  {/* Acceptance rate */}
                  <td className="py-3 px-3 text-right">
                    <span className={
                      cat.acceptance_rate >= 0.7 ? 'text-green-700' :
                      cat.acceptance_rate >= 0.4 ? 'text-amber-700' : 'text-red-700'
                    }>
                      {formatPct(cat.acceptance_rate)}
                    </span>
                  </td>

                  {/* Avg confidence */}
                  <td className="py-3 px-3 text-right text-gray-700">
                    {formatPct(cat.avg_confidence)}
                  </td>

                  {/* 7d revenue lift */}
                  <td className="py-3 px-3 text-right">
                    <span className={
                      cat.avg_revenue_lift_7d === null ? 'text-gray-400' :
                      cat.avg_revenue_lift_7d >= 0 ? 'text-green-700 font-medium' : 'text-red-700'
                    }>
                      {formatLift(cat.avg_revenue_lift_7d)}
                    </span>
                  </td>

                  {/* Data quality */}
                  <td className="py-3 px-3">
                    <DataQualityBar score={cat.data_quality_score} />
                  </td>

                  {/* Experiment status */}
                  <td className="py-3 px-3">
                    {cat.converged_strategy ? (
                      <Badge variant="success">
                        <CheckCircle className="w-3 h-3 mr-1 inline" />
                        {cat.converged_strategy}
                      </Badge>
                    ) : cat.active_experiment ? (
                      <Badge variant="info">
                        <FlaskConical className="w-3 h-3 mr-1 inline" />
                        Testing
                      </Badge>
                    ) : (
                      <Badge variant="default">No test</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}


