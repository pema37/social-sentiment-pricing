'use client';

// Recommendation Detail Page
// Full details of a price recommendation with actions

import { useState, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Zap,
  Package,
  BarChart3,
  FileText,
  ExternalLink,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { ConfidenceIndicator } from '@/components/features/pricing';
import { cn, formatCurrency, formatPercentage, formatDate, formatRelativeTime } from '@/lib/utils';
import {
  useRecommendation,
  useApproveRecommendation,
  useRejectRecommendation,
} from '@/lib/hooks/use-pricing';
import { useProduct } from '@/lib/hooks/use-products';
import type { RecommendationStatus } from '@/types';

// ============================================
// BUG FIX #1: Helper to format nested objects
// Prevents [object Object] from displaying
// ============================================
function formatFactorValue(value: unknown): string {
  if (value === null || value === undefined) {
    return 'N/A';
  }
  if (typeof value === 'number') {
    // Format percentages (values between -1 and 1) nicely
    if (Math.abs(value) <= 1 && value !== 0 && value !== 1 && value !== -1) {
      return `${(value * 100).toFixed(1)}%`;
    }
    return value.toFixed(2);
  }
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return 'None';
    return value.map(v => formatFactorValue(v)).join(', ');
  }
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    const entries = Object.entries(obj);
    if (entries.length === 0) return 'N/A';
    // Show key-value pairs for small objects
    if (entries.length <= 3) {
      return entries
        .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${formatFactorValue(v)}`)
        .join(' | ');
    }
    return `${entries.length} items`;
  }
  return String(value);
}

// ============================================
// STATUS CONFIG
// ============================================

const statusConfig: Record<RecommendationStatus, {
  label: string;
  color: string;
  bgColor: string;
  icon: typeof Clock;
}> = {
  pending: {
    label: 'Pending Review',
    color: 'text-yellow-800',
    bgColor: 'bg-yellow-100',
    icon: Clock,
  },
  auto_approved: {
    label: 'Auto-Approved',
    color: 'text-blue-800',
    bgColor: 'bg-blue-100',
    icon: Zap,
  },
  approved: {
    label: 'Approved',
    color: 'text-green-800',
    bgColor: 'bg-green-100',
    icon: CheckCircle2,
  },
  rejected: {
    label: 'Rejected',
    color: 'text-red-800',
    bgColor: 'bg-red-100',
    icon: XCircle,
  },
  applied: {
    label: 'Applied',
    color: 'text-emerald-800',
    bgColor: 'bg-emerald-100',
    icon: CheckCircle2,
  },
  expired: {
    label: 'Expired',
    color: 'text-gray-800',
    bgColor: 'bg-gray-100',
    icon: AlertCircle,
  },
};

// ============================================
// COMPONENT
// ============================================

export default function RecommendationDetailPage() {
  const router = useRouter();
  const params = useParams();
  const recommendationId = params.id as string;

  // Fetch recommendation
  const {
    data: recommendation,
    isLoading,
    isError,
    refetch,
  } = useRecommendation(recommendationId);

  // Fetch product details
  const { data: product } = useProduct(recommendation?.product_id ?? '');

  // Mutations
  const approveMutation = useApproveRecommendation();
  const rejectMutation = useRejectRecommendation();

  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectError, setRejectError] = useState('');

  const isPending = recommendation?.status === 'pending';
  const isIncrease = (recommendation?.change_percent ?? 0) > 0;

  // Handle approve
  const handleApprove = useCallback(async () => {
    try {
      await approveMutation.mutateAsync({ id: recommendationId });
      toast.success('Recommendation approved');
      refetch();
    } catch (error) {
      toast.error('Failed to approve recommendation');
      console.error('Approve error:', error);
    }
  }, [recommendationId, approveMutation, refetch]);

  // Handle reject — open modal
  const handleReject = useCallback(() => {
    setShowRejectModal(true);
    setRejectReason('');
    setRejectError('');
  }, []);

  // Handle reject confirm from modal
  const handleRejectConfirm = useCallback(async () => {
    const trimmed = rejectReason.trim();
    if (trimmed.length < 10) {
      setRejectError('Please provide a more detailed reason (at least 10 characters)');
      return;
    }

    try {
      await rejectMutation.mutateAsync({ id: recommendationId, data: { reason: trimmed } });
      toast.success('Recommendation rejected');
      setShowRejectModal(false);
      refetch();
    } catch (error) {
      toast.error('Failed to reject recommendation');
      console.error('Reject error:', error);
    }
  }, [recommendationId, rejectReason, rejectMutation, refetch]);

  // Loading state
  if (isLoading) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push('/pricing')}
          className="mb-6"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Recommendations
        </Button>

        <div className="space-y-6">
          <div className="animate-pulse">
            <div className="h-8 w-64 bg-gray-200 rounded mb-2" />
            <div className="h-5 w-48 bg-gray-100 rounded" />
          </div>

          {[...Array(3)].map((_, i) => (
            <Card key={i} padding="md">
              <div className="animate-pulse space-y-4">
                <div className="h-6 w-40 bg-gray-200 rounded" />
                <div className="h-20 w-full bg-gray-100 rounded-lg" />
              </div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (isError || !recommendation) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push('/pricing')}
          className="mb-6"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Recommendations
        </Button>

        <Card padding="md" className="bg-red-50 border-red-200">
          <h3 className="text-red-800 font-medium mb-2">Error Loading Recommendation</h3>
          <p className="text-red-600 text-sm mb-4">
            The recommendation could not be found or there was an error loading it.
          </p>
          <Button variant="secondary" size="sm" onClick={() => router.push('/pricing')}>
            Return to Recommendations
          </Button>
        </Card>
      </div>
    );
  }

  const statusInfo = statusConfig[recommendation.status];
  const StatusIcon = statusInfo.icon;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push('/pricing')}
          className="mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Recommendations
        </Button>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Price Recommendation
            </h1>
            <p className="text-gray-600 mt-1">
              Created {formatRelativeTime(recommendation.created_at)}
            </p>
          </div>

          {/* Status Badge */}
          <span
            className={cn(
              'inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium',
              statusInfo.bgColor,
              statusInfo.color
            )}
          >
            <StatusIcon className="h-4 w-4" />
            {statusInfo.label}
          </span>
        </div>
      </div>

      <div className="space-y-6">
        {/* Price Change Card */}
        <Card padding="md">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-gray-600" />
            Price Change
          </h2>

          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div className="text-center">
              <p className="text-sm text-gray-500 uppercase tracking-wide mb-1">
                Current Price
              </p>
              <p className="text-3xl font-bold text-gray-700">
                {formatCurrency(parseFloat(recommendation.current_price))}
              </p>
            </div>

            <div className="flex flex-col items-center px-6">
              {isIncrease ? (
                <TrendingUp className="h-8 w-8 text-green-500 mb-2" />
              ) : (
                <TrendingDown className="h-8 w-8 text-red-500 mb-2" />
              )}
              <span
                className={cn(
                  'px-4 py-2 rounded-full text-lg font-bold',
                  isIncrease
                    ? 'bg-green-100 text-green-800'
                    : 'bg-red-100 text-red-800'
                )}
              >
                {formatPercentage(recommendation.change_percent)}
              </span>
            </div>

            <div className="text-center">
              <p className="text-sm text-gray-500 uppercase tracking-wide mb-1">
                Recommended Price
              </p>
              <p className="text-3xl font-bold text-gray-900">
                {formatCurrency(parseFloat(recommendation.recommended_price))}
              </p>
            </div>
          </div>

          {/* Confidence Score */}
          <div className="mt-4 p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">Confidence Score</span>
              <ConfidenceIndicator score={recommendation.confidence_score} size="md" />
            </div>
          </div>
        </Card>

        {/* Product Info Card */}
        <Card padding="md">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Package className="h-5 w-5 text-gray-600" />
            Product Information
          </h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500 mb-1">Product Name</p>
              <p className="font-medium text-gray-900">
                {product?.name ?? 'Loading...'}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500 mb-1">SKU</p>
              <p className="font-medium text-gray-900">
                {product?.sku ?? 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500 mb-1">Product ID</p>
              <p className="font-mono text-sm text-gray-600">
                {recommendation.product_id}
              </p>
            </div>
            {product && (
              <div>
                <p className="text-sm text-gray-500 mb-1">View Product</p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => router.push(`/products/${recommendation.product_id}`)}
                  className="p-0 h-auto"
                >
                  <ExternalLink className="h-4 w-4 mr-1" />
                  Open Product
                </Button>
              </div>
            )}
          </div>
        </Card>

        {/* Reasoning Card */}
        <Card padding="md">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <FileText className="h-5 w-5 text-gray-600" />
            Reasoning
          </h2>

          <p className="text-gray-700 leading-relaxed">
            {recommendation.reasoning}
          </p>
        </Card>

        {/* Contributing Factors Card - BUG FIX #1 APPLIED HERE */}
        <Card padding="md">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Contributing Factors
          </h2>

          {recommendation.factors && Object.keys(recommendation.factors).length > 0 ? (
            <div className="space-y-3">
              {Object.entries(recommendation.factors).map(([key, value]) => (
                <div
                  key={key}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <span className="text-sm font-medium text-gray-700 capitalize">
                    {key.replace(/_/g, ' ')}
                  </span>
                  <span className="text-sm text-gray-900">
                    {/* BUG FIX: Changed from String(value) to formatFactorValue(value) */}
                    {formatFactorValue(value)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No detailed factors available.</p>
          )}
        </Card>

        {/* Timeline / Metadata Card */}
        <Card padding="md">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Timeline
          </h2>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">Created</span>
              <span className="text-sm text-gray-900">
                {formatDate(recommendation.created_at)}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">Expires</span>
              <span className="text-sm text-gray-900">
                {formatDate(recommendation.expires_at)}
              </span>
            </div>

            {recommendation.reviewed_at && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">Reviewed</span>
                <span className="text-sm text-gray-900">
                  {formatDate(recommendation.reviewed_at)}
                </span>
              </div>
            )}

            {recommendation.applied_at && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">Applied</span>
                <span className="text-sm text-gray-900">
                  {formatDate(recommendation.applied_at)}
                </span>
              </div>
            )}

            {recommendation.rejection_reason && (
              <div className="pt-3 border-t border-gray-100">
                <p className="text-sm text-gray-500 mb-1">Rejection Reason</p>
                <p className="text-sm text-red-700 bg-red-50 p-3 rounded-lg">
                  {recommendation.rejection_reason}
                </p>
              </div>
            )}

            {recommendation.rule_id && (
              <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                <span className="text-sm text-gray-500">Triggered by Rule</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => router.push(`/pricing/rules/${recommendation.rule_id}`)}
                  className="p-0 h-auto"
                >
                  <ExternalLink className="h-4 w-4 mr-1" />
                  View Rule
                </Button>
              </div>
            )}
          </div>
        </Card>

        {/* Actions */}
        {isPending && (
          <Card padding="md" className="bg-yellow-50 border-yellow-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Pending Action Required
            </h2>
            <p className="text-gray-600 mb-4">
              Review the recommendation details above and approve or reject this price change.
            </p>

            <div className="flex items-center gap-3">
              <Button
                variant="primary"
                onClick={handleApprove}
                disabled={approveMutation.isPending || rejectMutation.isPending}
              >
                <CheckCircle2 className="h-4 w-4 mr-2" />
                Approve
              </Button>
              <Button
                variant="danger"
                onClick={handleReject}
                disabled={approveMutation.isPending || rejectMutation.isPending}
              >
                <XCircle className="h-4 w-4 mr-2" />
                Reject
              </Button>
            </div>
          </Card>
        )}
      </div>

      {/* Reject Reason Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => !rejectMutation.isPending && setShowRejectModal(false)}
            aria-hidden="true"
          />
          <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6" role="dialog" aria-modal="true">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Reject Recommendation</h2>
            <form onSubmit={(e) => { e.preventDefault(); handleRejectConfirm(); }}>
              <div className="mb-4">
                <label htmlFor="rejection-reason" className="block text-sm font-medium text-gray-700 mb-2">
                  Reason for Rejection
                </label>
                <textarea
                  id="rejection-reason"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Explain why this recommendation should not be applied..."
                  rows={4}
                  className={cn(
                    'w-full px-3 py-2 border rounded-lg text-sm',
                    'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                    'placeholder:text-gray-400',
                    rejectError ? 'border-red-300' : 'border-gray-300'
                  )}
                  disabled={rejectMutation.isPending}
                  autoFocus
                />
                {rejectError && <p className="mt-1 text-sm text-red-600">{rejectError}</p>}
              </div>
              <div className="flex justify-end gap-3">
                <Button variant="secondary" size="sm" type="button" onClick={() => setShowRejectModal(false)} disabled={rejectMutation.isPending}>
                  Cancel
                </Button>
                <Button variant="danger" size="sm" type="submit" disabled={rejectMutation.isPending || !rejectReason.trim()}>
                  {rejectMutation.isPending ? 'Rejecting...' : 'Reject'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
