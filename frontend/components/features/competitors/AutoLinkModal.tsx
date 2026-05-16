'use client';

// frontend/components/features/competitors/AutoLinkModal.tsx

import { useState } from 'react';
import {
  Link as LinkIcon,
  AlertTriangle,
  CheckCircle,
  X,
  Zap,
  Settings,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { MatchConfidenceBadge } from './MatchConfidenceBadge';
import type { MatchedProduct } from '@/types';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface AutoLinkModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (threshold: number) => void;
  products: MatchedProduct[];
  productName: string;
  isLinking?: boolean;
}

interface LinkPreviewProps {
  products: MatchedProduct[];
  threshold: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function LinkPreview({ products, threshold }: LinkPreviewProps) {
  const willBeLinked = products.filter((p) => p.confidence_score >= threshold);
  const willBeSkipped = products.filter((p) => p.confidence_score < threshold);

  return (
    <div className="space-y-4">
      {/* Will be linked */}
      {willBeLinked.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-4 h-4 text-green-600" />
            <span className="text-sm font-medium text-green-800">
              {willBeLinked.length} product{willBeLinked.length !== 1 ? 's' : ''} will be linked
            </span>
          </div>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {willBeLinked.map((product, idx) => (
              <div
                key={`${product.url}-${idx}`}
                className="flex items-center justify-between p-2 bg-green-50 rounded-lg text-sm"
              >
                <div className="flex-1 min-w-0 mr-2">
                  <p className="font-medium text-gray-900 truncate">{product.title}</p>
                  <p className="text-gray-500 text-xs">{product.merchant}</p>
                </div>
                <div className="flex items-center gap-2">
                  {product.price && (
                    <span className="text-gray-700">${product.price}</span>
                  )}
                  <MatchConfidenceBadge score={product.confidence_score} size="sm" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Will be skipped */}
      {willBeSkipped.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-yellow-600" />
            <span className="text-sm font-medium text-yellow-800">
              {willBeSkipped.length} product{willBeSkipped.length !== 1 ? 's' : ''} below threshold
            </span>
          </div>
          <div className="space-y-2 max-h-32 overflow-y-auto">
            {willBeSkipped.slice(0, 5).map((product, idx) => (
              <div
                key={`${product.url}-${idx}`}
                className="flex items-center justify-between p-2 bg-gray-50 rounded-lg text-sm opacity-60"
              >
                <div className="flex-1 min-w-0 mr-2">
                  <p className="text-gray-700 truncate">{product.title}</p>
                  <p className="text-gray-400 text-xs">{product.merchant}</p>
                </div>
                <MatchConfidenceBadge score={product.confidence_score} size="sm" />
              </div>
            ))}
            {willBeSkipped.length > 5 && (
              <p className="text-xs text-gray-500 text-center">
                +{willBeSkipped.length - 5} more
              </p>
            )}
          </div>
        </div>
      )}

      {/* No matches */}
      {willBeLinked.length === 0 && (
        <div className="text-center py-4">
          <AlertTriangle className="w-8 h-8 text-yellow-500 mx-auto mb-2" />
          <p className="text-gray-600">
            No products meet the current threshold.
          </p>
          <p className="text-sm text-gray-500">
            Try lowering the confidence threshold.
          </p>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function AutoLinkModal({
  isOpen,
  onClose,
  onConfirm,
  products,
  productName,
  isLinking = false,
}: AutoLinkModalProps) {
  const [threshold, setThreshold] = useState(0.8);

  const eligibleCount = products.filter((p) => p.confidence_score >= threshold).length;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <Card className="relative w-full max-w-lg bg-white shadow-xl">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5 text-blue-600" />
              <h2 className="text-lg font-semibold text-gray-900">
                Auto-Link Competitors
              </h2>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body */}
          <div className="p-4 space-y-4">
            {/* Product info */}
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-sm text-gray-500">Linking competitors for:</p>
              <p className="font-medium text-gray-900">{productName}</p>
            </div>

            {/* Threshold slider */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="flex items-center gap-1 text-sm font-medium text-gray-700">
                  <Settings className="w-4 h-4" />
                  Confidence Threshold
                </label>
                <Badge variant={threshold >= 0.8 ? 'success' : threshold >= 0.5 ? 'warning' : 'danger'}>
                  {Math.round(threshold * 100)}%
                </Badge>
              </div>
              <input
                type="range"
                min="30"
                max="95"
                step="5"
                value={threshold * 100}
                onChange={(e) => setThreshold(parseInt(e.target.value) / 100)}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>30% (More matches)</span>
                <span>95% (Best matches only)</span>
              </div>
            </div>

            {/* Preview */}
            <LinkPreview products={products} threshold={threshold} />

            {/* Info */}
            <div className="bg-blue-50 rounded-lg p-3">
              <div className="flex gap-2">
                <AlertTriangle className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
                <div className="text-sm text-blue-800">
                  <p className="font-medium">What happens next:</p>
                  <ul className="mt-1 list-disc list-inside text-blue-700 space-y-1">
                    <li>Competitor products will be created automatically</li>
                    <li>Price tracking will begin for linked products</li>
                    <li>You can unlink products later if needed</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 p-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
            <Button variant="secondary" onClick={onClose} disabled={isLinking}>
              Cancel
            </Button>
            <Button
              onClick={() => onConfirm(threshold)}
              disabled={eligibleCount === 0 || isLinking}
            >
              {isLinking ? (
                <>
                  <div className="w-4 h-4 mr-2 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Linking...
                </>
              ) : (
                <>
                  <LinkIcon className="w-4 h-4 mr-2" />
                  Link {eligibleCount} Product{eligibleCount !== 1 ? 's' : ''}
                </>
              )}
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default AutoLinkModal;


