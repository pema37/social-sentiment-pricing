// components/products/PriceHistoryCard.tsx
'use client';

import { History, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { usePriceHistory } from '@/lib/hooks/use-products';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface PriceHistoryCardProps {
  productId: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(value);
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <History className="h-5 w-5 text-gray-500" />
        <h3 className="font-semibold text-gray-900">Price History</h3>
      </div>
      <div className="animate-pulse space-y-3">
        {[1, 2, 3].map(i => (
          <div key={i} className="flex justify-between">
            <div className="h-4 bg-gray-200 rounded w-20" />
            <div className="h-4 bg-gray-200 rounded w-16" />
          </div>
        ))}
      </div>
    </Card>
  );
}

function EmptyState() {
  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <History className="h-5 w-5 text-gray-500" />
        <h3 className="font-semibold text-gray-900">Price History</h3>
      </div>
      <p className="text-sm text-gray-500 text-center py-4">
        No price history available yet.
      </p>
    </Card>
  );
}

interface ChangeIconProps {
  change: number;
}

function ChangeIcon({ change }: ChangeIconProps) {
  if (change > 0) {
    return <TrendingUp className="h-4 w-4 text-green-500" />;
  }
  if (change < 0) {
    return <TrendingDown className="h-4 w-4 text-red-500" />;
  }
  return <Minus className="h-4 w-4 text-gray-400" />;
}

interface PriceHistoryItemProps {
  price: number;
  date: string;
  previousPrice?: number;
  source?: string;
}

function PriceHistoryItem({ price, date, previousPrice, source }: PriceHistoryItemProps) {
  const change = previousPrice ? ((price - previousPrice) / previousPrice) * 100 : 0;
  
  const changeColorClass = change > 0
    ? 'text-green-600'
    : change < 0
      ? 'text-red-600'
      : 'text-gray-500';

  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
      <div className="flex items-center gap-2">
        <ChangeIcon change={change} />
        <div>
          <p className="font-medium text-gray-900">{formatCurrency(price)}</p>
          <p className="text-xs text-gray-500">{formatDate(date)}</p>
        </div>
      </div>
      <div className="text-right">
        {previousPrice && (
          <p className={`text-sm font-medium ${changeColorClass}`}>
            {change >= 0 && '+'}
            {change.toFixed(1)}%
          </p>
        )}
        {source && (
          <p className="text-xs text-gray-400 capitalize">{source}</p>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function PriceHistoryCard({ productId }: PriceHistoryCardProps) {
  const { data, isLoading } = usePriceHistory(productId, { limit: 10 });

  if (isLoading) {
    return <LoadingState />;
  }

  const history = data || [];

  if (history.length === 0) {
    return <EmptyState />;
  }

  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <History className="h-5 w-5 text-gray-500" />
        <h3 className="font-semibold text-gray-900">Price History</h3>
        <span className="text-xs text-gray-400 ml-auto">
          Last {history.length} changes
        </span>
      </div>

      <div className="space-y-1">
        {history.map((item, index) => (
          <PriceHistoryItem
            key={item.id || index}
            price={item.price}
            date={item.created_at}
            previousPrice={history[index + 1]?.price}
            source={item.change_reason || undefined}
          />
        ))}
      </div>
    </Card>
  );
}

export default PriceHistoryCard;
