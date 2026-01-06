// components/products/AutoPricingCard.tsx
'use client';

import { Zap, Clock } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { useToggleAutoPricing, type Product } from '@/lib/hooks/use-products';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface AutoPricingCardProps {
  product: Product;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function safeParseMultiplier(value: unknown, defaultValue = 0.2): number {
  if (value == null) return defaultValue;
  const num = typeof value === 'number' ? value : parseFloat(String(value));
  return isNaN(num) ? defaultValue : num;
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

interface ToggleSwitchProps {
  enabled: boolean;
  onToggle: () => void;
  disabled?: boolean;
}

function ToggleSwitch({ enabled, onToggle, disabled }: ToggleSwitchProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      className={`relative w-12 h-6 rounded-full transition-colors ${
        enabled ? 'bg-green-500' : 'bg-gray-300'
      } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      <span
        className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
          enabled ? 'translate-x-7' : 'translate-x-1'
        }`}
      />
    </button>
  );
}

interface InfoRowProps {
  label: string;
  value: string | React.ReactNode;
}

function InfoRow({ label, value }: InfoRowProps) {
  return (
    <div className="flex justify-between items-center py-2">
      <span className="text-sm text-gray-600">{label}</span>
      <span className="text-sm font-medium text-gray-900">{value}</span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function AutoPricingCard({ product }: AutoPricingCardProps) {
  const toggleAutoPricing = useToggleAutoPricing();

  const handleToggle = () => {
    toggleAutoPricing.mutate({
      id: product.id,
      enabled: !product.auto_pricing_enabled,
    });
  };

  // Safe multiplier calculation
  const multiplierPercent = (safeParseMultiplier(product.sentiment_multiplier) * 100).toFixed(0);

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Zap className="h-5 w-5 text-yellow-500" />
          <h3 className="font-semibold text-gray-900">Auto-Pricing</h3>
        </div>
        <ToggleSwitch
          enabled={product.auto_pricing_enabled}
          onToggle={handleToggle}
          disabled={toggleAutoPricing.isPending}
        />
      </div>

      <div className="divide-y divide-gray-100">
        <InfoRow
          label="Status"
          value={
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                product.auto_pricing_enabled
                  ? 'bg-green-100 text-green-800'
                  : 'bg-gray-100 text-gray-600'
              }`}
            >
              {product.auto_pricing_enabled ? 'Enabled' : 'Disabled'}
            </span>
          }
        />
        <InfoRow
          label="Sentiment Multiplier"
          value={`${multiplierPercent}%`}
        />
        <InfoRow
          label="Last Updated"
          value={
            <span className="flex items-center gap-1 text-gray-500">
              <Clock className="h-3 w-3" />
              {formatDate(product.updated_at)}
            </span>
          }
        />
      </div>

      {product.auto_pricing_enabled && (
        <p className="mt-4 text-xs text-gray-500 bg-yellow-50 p-2 rounded">
          Prices will automatically adjust based on sentiment analysis within your min/max bounds.
        </p>
      )}
    </Card>
  );
}

export default AutoPricingCard;


