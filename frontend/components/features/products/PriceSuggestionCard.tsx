// components/products/PriceSuggestionCard.tsx
// PATCHED: Added error code handling and competitor-only badge
// PATCHED (2025-01-07): Fixed parseApiError to handle ApiError class from client.ts
'use client';

import { TrendingUp, Check, RefreshCw, AlertCircle, Info, ExternalLink } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import Link from 'next/link';
import {
  usePriceSuggestion,
  useApplyPriceSuggestion,
} from '@/lib/hooks/use-products';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface PriceSuggestionCardProps {
  productId: string;
  currentPrice: string | number;
}

interface ApiErrorDetails {
  error?: string;
  error_code?: string;
  suggestion?: string;
  detail?: string | Array<{ msg?: string; loc?: string[] }>;
  message?: string;
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

function calculateChange(suggested: number, current: number): number {
  if (!current || current === 0) return 0;
  return ((suggested - current) / current) * 100;
}

// ========== PATCH: Fixed parseApiError to handle ApiError class from client.ts ==========
function parseApiError(error: unknown): { message: string; code?: string; suggestion?: string } {
  if (!error) return { message: 'Unknown error' };
  
  // Handle our ApiError class from lib/api/client.ts
  // ApiError has: status (number), message (string), details (unknown)
  if (error instanceof Error) {
    const err = error as Error & { 
      status?: number; 
      details?: ApiErrorDetails;
    };
    
    // If it's our ApiError with details, extract the good stuff
    if ('details' in err && err.details && typeof err.details === 'object') {
      const details = err.details;
      
      // Handle FastAPI validation errors (detail is an array)
      if (Array.isArray(details.detail)) {
        const messages = details.detail
          .map((item) => item.msg || 'Validation error')
          .join(', ');
        return {
          message: messages || err.message,
          code: details.error_code,
          suggestion: details.suggestion,
        };
      }
      
      // Handle string detail
      if (typeof details.detail === 'string') {
        return {
          message: details.detail,
          code: details.error_code,
          suggestion: details.suggestion,
        };
      }
      
      // Handle error field
      if (details.error) {
        return {
          message: details.error,
          code: details.error_code,
          suggestion: details.suggestion,
        };
      }
      
      // Has details but no specific message - use the Error message
      return {
        message: err.message,
        code: details.error_code,
        suggestion: details.suggestion,
      };
    }
    
    // Plain Error without details - just use message
    // But make the "Network error" more helpful
    if (err.message === 'Network error. Please try again.') {
      return {
        message: 'Unable to fetch price suggestion. Please check your connection and try again.',
      };
    }
    
    return { message: err.message };
  }
  
  // Handle plain objects (shouldn't happen with our client, but just in case)
  if (typeof error === 'object' && error !== null) {
    const err = error as Record<string, unknown>;
    
    // Check for response.data (axios style - legacy support)
    const responseData = (err.response as Record<string, unknown>)?.data as ApiErrorDetails;
    if (responseData) {
      return {
        message: responseData.error || 
                 (typeof responseData.detail === 'string' ? responseData.detail : '') || 
                 responseData.message || 
                 'Request failed',
        code: responseData.error_code,
        suggestion: responseData.suggestion,
      };
    }
    
    // Direct error object with error_code
    const directErr = err as ApiErrorDetails;
    if (directErr.error_code || directErr.error || directErr.detail) {
      return {
        message: directErr.error || 
                 (typeof directErr.detail === 'string' ? directErr.detail : '') || 
                 directErr.message || 
                 'Request failed',
        code: directErr.error_code,
        suggestion: directErr.suggestion,
      };
    }
  }
  
  return { message: String(error) };
}
// ========== END PATCH ==========

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="h-5 w-5 text-blue-500" />
        <h3 className="font-semibold text-gray-900">Price Suggestion</h3>
      </div>
      <div className="animate-pulse space-y-3">
        <div className="h-8 bg-gray-200 rounded w-24" />
        <div className="h-4 bg-gray-200 rounded w-32" />
      </div>
    </Card>
  );
}

// ========== PATCH: Enhanced error state with action buttons ==========
function ErrorState({ 
  message, 
  code,
  suggestion,
  onRetry 
}: { 
  message: string; 
  code?: string;
  suggestion?: string;
  onRetry: () => void;
}) {
  // Show "Go to Integrations" for link-related errors
  const showIntegrationsLink = 
    code === 'MISSING_INTEGRATION_LINK' || 
    code === 'INVALID_CREDENTIALS' ||
    code === 'INTEGRATION_NOT_FOUND' ||
    code === 'INTEGRATION_INACTIVE' ||
    code === 'SYNC_DISABLED';

  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="h-5 w-5 text-blue-500" />
        <h3 className="font-semibold text-gray-900">Price Suggestion</h3>
      </div>
      <div className="flex items-start gap-2 mb-3">
        <AlertCircle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="text-sm text-gray-600">{message}</p>
          {suggestion && (
            <p className="text-xs text-gray-500">{suggestion}</p>
          )}
        </div>
      </div>
      
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RefreshCw className="h-4 w-4 mr-1" />
          Retry
        </Button>
        
        {showIntegrationsLink && (
          <Link href="/integrations">
            <Button variant="secondary" size="sm">
              <ExternalLink className="h-4 w-4 mr-1" />
              Go to Integrations
            </Button>
          </Link>
        )}
      </div>
    </Card>
  );
}
// ========== END PATCH ==========

interface PriceChangeIndicatorProps {
  change: number;
}

function PriceChangeIndicator({ change }: PriceChangeIndicatorProps) {
  const isPositive = change > 0;
  const isNegative = change < 0;
  
  const colorClass = isPositive
    ? 'text-green-600'
    : isNegative
      ? 'text-red-600'
      : 'text-gray-500';

  return (
    <span className={`text-sm font-medium ${colorClass}`}>
      {isPositive && '+'}
      {(Number(change ?? 0)).toFixed(1)}% from current
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function PriceSuggestionCard({ productId, currentPrice }: PriceSuggestionCardProps) {
  const {
    data: suggestion,
    isLoading,
    error,
    refetch,
  } = usePriceSuggestion(productId);

  const applyPrice = useApplyPriceSuggestion();

  // Convert currentPrice to number
  const currentPriceNum = typeof currentPrice === 'string' ? parseFloat(currentPrice) : currentPrice;

  // Loading state
  if (isLoading) {
    return <LoadingState />;
  }

  // ========== PATCH: Use parseApiError for better error display ==========
  if (error) {
    const { message, code, suggestion: errorSuggestion } = parseApiError(error);
    return (
      <ErrorState 
        message={message}
        code={code}
        suggestion={errorSuggestion}
        onRetry={() => refetch()} 
      />
    );
  }
  // ========== END PATCH ==========

  // No suggestion data returned
  if (!suggestion) {
    return (
      <ErrorState 
        message="No suggestion data available. Try refreshing." 
        onRetry={() => refetch()} 
      />
    );
  }

  // Suggestion exists - always show it, even with low confidence or no change
  const suggestedPrice = Number(suggestion.suggested_price) || currentPriceNum;
  const change = calculateChange(suggestedPrice, currentPriceNum);
  const confidence = Number(suggestion.confidence) || 0;
  const isLowConfidence = confidence < 0.3;
  const noChangeRecommended = Math.abs(change) < 0.01;

  // ========== PATCH: Detect competitor-only recommendations (FIXED TS ERROR) ==========
  // Safely access factors - cast suggestion to unknown first to avoid TS error
  const suggestionAny = suggestion as unknown as Record<string, unknown>;
  const factors = suggestionAny.factors as Record<string, unknown> | undefined;
  const dataSource = factors?.data_source ?? suggestionAny.data_source;
  const matchDetails = factors?.match_details as Record<string, unknown> | undefined;
  const isCompetitorOnly = 
    dataSource === 'competitor_only' || 
    matchDetails?.rule_type === 'competitor_fallback';
  const competitorPrice = matchDetails?.competitor_price as number | undefined;
  // ========== END PATCH ==========

  const handleApply = () => {
    applyPrice.mutate(
      {
        id: productId,
        price: suggestedPrice,
      },
      {
        // ========== PATCH: Handle apply errors with codes ==========
        onError: (err) => {
          const { message, code } = parseApiError(err);
          console.error('Apply price failed:', { message, code });
          // Toast is handled by the mutation hook, but we log for debugging
        },
        // ========== END PATCH ==========
      }
    );
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-blue-500" />
          <h3 className="font-semibold text-gray-900">Price Suggestion</h3>
        </div>
        
        {/* ========== PATCH: Show competitor-only badge ========== */}
        {isCompetitorOnly && (
          <span className="inline-flex items-center px-2 py-1 text-xs font-medium bg-blue-50 text-blue-700 rounded-full border border-blue-200">
            <Info className="h-3 w-3 mr-1" />
            Competitor-based
          </span>
        )}
        {/* ========== END PATCH ========== */}
      </div>

      <div className="space-y-4">
        {/* Suggested Price */}
        <div>
          <p className="text-3xl font-bold text-blue-600">
            {formatCurrency(suggestedPrice)}
          </p>
          <PriceChangeIndicator change={change} />
        </div>

        {/* ========== PATCH: Show competitor price context ========== */}
        {isCompetitorOnly && competitorPrice && (
          <div className="flex items-center gap-2 text-xs text-gray-500 bg-gray-50 p-2 rounded">
            <Info className="h-3 w-3" />
            <span>Based on competitor price: {formatCurrency(competitorPrice)}</span>
          </div>
        )}
        {/* ========== END PATCH ========== */}

        {/* Low confidence or no change warning - but not for competitor-only */}
        {(isLowConfidence || noChangeRecommended) && !isCompetitorOnly && (
          <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
            <AlertCircle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
            <p className="text-sm text-amber-700">
              {noChangeRecommended 
                ? 'Current price is optimal based on available data.'
                : 'Limited data available. Consider adding more sentiment keywords or competitor links.'}
            </p>
          </div>
        )}

        {/* ========== PATCH: Competitor-only info box ========== */}
        {isCompetitorOnly && (
          <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <Info className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
            <p className="text-sm text-blue-700">
              This suggestion is based on competitor pricing only. Add sentiment keywords for more accurate recommendations.
            </p>
          </div>
        )}
        {/* ========== END PATCH ========== */}

        {/* Reasoning */}
        {suggestion.reasoning && (
          <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg">
            {suggestion.reasoning}
          </p>
        )}

        {/* Confidence */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">Confidence:</span>
          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${
                confidence >= 0.7 ? 'bg-green-500' :
                confidence >= 0.5 ? 'bg-blue-500' : 
                confidence >= 0.3 ? 'bg-amber-400' : 'bg-gray-400'
              }`}
              style={{ width: `${Math.max(confidence * 100, 5)}%` }}
            />
          </div>
          <span className="text-sm font-medium text-gray-700">
            {(confidence * 100).toFixed(0)}%
          </span>
        </div>

        {/* Apply Button - only show if there's a price change */}
        {!noChangeRecommended && (
          <Button
            onClick={handleApply}
            isLoading={applyPrice.isPending}
            className="w-full"
          >
            <Check className="h-4 w-4 mr-2" />
            Apply Suggested Price
          </Button>
        )}
      </div>
    </Card>
  );
}

export default PriceSuggestionCard;


