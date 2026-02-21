// Pricing Page
// Lists price recommendations with filtering and approve/reject actions

'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { DollarSign, Settings, RefreshCw, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { AIBadge } from '@/components/ui/ai-badge';
import {
  RecommendationsList,
  RecommendationsListSkeleton,
} from '@/components/features/pricing';
import {
  useRecommendations,
  useApproveRecommendation,
  useRejectRecommendation,
  usePricingRecommendationStats,
} from '@/lib/hooks/use-pricing';
import { useProducts } from '@/lib/hooks/use-products';
import { api } from '@/lib/api/client';
import type { RecommendationStatus } from '@/types';

// ============================================
// STAT CARD
// ============================================

interface StatCardProps {
  label: string;
  value: string | number;
  highlight?: boolean;
}

function StatCard({ label, value, highlight }: StatCardProps) {
  return (
    <Card
      padding="sm"
      className={highlight ? 'bg-yellow-50 border-yellow-200' : ''}
    >
      <p className="text-sm text-gray-600 mb-1">{label}</p>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
    </Card>
  );
}

// ============================================
// PAGE COMPONENT
// ============================================

export default function PricingPage() {
  const router = useRouter();
  const [filterStatus, setFilterStatus] = useState<RecommendationStatus | 'all'>('pending');
  const [actionLoadingId, setActionLoadingId] = useState<string | undefined>();
  const [isGenerating, setIsGenerating] = useState(false);

  // Fetch recommendations
  const {
    data: recommendationsData,
    isLoading: isLoadingRecommendations,
    isError: isRecommendationsError,
    refetch: refetchRecommendations,
  } = useRecommendations({
    page_size: 50,
  });

  // Fetch stats
  const { data: stats, refetch: refetchStats } = usePricingRecommendationStats();

  // Fetch products for names
  const { data: productsData, isLoading: isLoadingProducts } = useProducts({
    page_size: 100,
  });

  // Mutations
  const approveMutation = useApproveRecommendation();
  const rejectMutation = useRejectRecommendation();

  // Build product name/sku maps
  const productNames: Record<string, string> = {};
  const productSkus: Record<string, string | null> = {};

  if (productsData?.items) {
    productsData.items.forEach((product) => {
      productNames[product.id] = product.name;
      productSkus[product.id] = product.sku;
    });
  }

  // Handle generate recommendations
  const handleGenerateRecommendations = useCallback(async () => {
    setIsGenerating(true);
    try {
      const result = await api.post<{
        message: string;
        products_checked: number;
        recommendations_created: number;
        results: Array<{
          product_id: string;
          product_name: string;
          success: boolean;
          recommendation_id?: string;
          message?: string;
          error?: string;
        }>;
      }>('/api/v1/pricing/recommendations/generate-all', {});

      if (result.recommendations_created > 0) {
        toast.success(
          `Generated ${result.recommendations_created} recommendation${result.recommendations_created > 1 ? 's' : ''} from ${result.products_checked} products`
        );
      } else {
        toast.info(
          `Checked ${result.products_checked} products. No new recommendations needed.`,
          {
            description: 'Products may already be optimally priced or no rules matched.',
          }
        );
      }

      // Refresh data
      refetchRecommendations();
      refetchStats();
    } catch (error) {
      console.error('Generate error:', error);
      toast.error('Failed to generate recommendations', {
        description: error instanceof Error ? error.message : 'Please try again',
      });
    } finally {
      setIsGenerating(false);
    }
  }, [refetchRecommendations, refetchStats]);

  // Handle approve
  const handleApprove = useCallback(
    async (id: string) => {
      setActionLoadingId(id);
      try {
        await approveMutation.mutateAsync({ id });
        toast.success('Recommendation approved');
        refetchRecommendations();
      } catch (error) {
        toast.error('Failed to approve recommendation');
        console.error('Approve error:', error);
      } finally {
        setActionLoadingId(undefined);
      }
    },
    [approveMutation, refetchRecommendations]
  );

  // Handle reject
  const handleReject = useCallback(
    async (id: string) => {
      const reason = window.prompt('Enter rejection reason:');
      if (!reason || reason.trim().length < 10) {
        toast.error('Please provide a reason (at least 10 characters)');
        return;
      }

      setActionLoadingId(id);
      try {
        await rejectMutation.mutateAsync({ id, data: { reason: reason.trim() } });
        toast.success('Recommendation rejected');
        refetchRecommendations();
      } catch (error) {
        toast.error('Failed to reject recommendation');
        console.error('Reject error:', error);
      } finally {
        setActionLoadingId(undefined);
      }
    },
    [rejectMutation, refetchRecommendations]
  );

  // Handle view details
  const handleView = useCallback(
    (id: string) => {
      router.push(`/pricing/recommendations/${id}`);
    },
    [router]
  );

  // Handle filter change
  const handleFilterChange = useCallback((status: RecommendationStatus | 'all') => {
    setFilterStatus(status);
  }, []);

  // Loading state
  const isLoading = isLoadingRecommendations || isLoadingProducts;

  // Error state
  if (isRecommendationsError) {
    return (
      <div className="p-6">
        <Card padding="md" className="bg-red-50 border-red-200">
          <h3 className="text-red-800 font-medium mb-2">Error Loading Recommendations</h3>
          <p className="text-red-600 text-sm mb-4">
            Something went wrong while fetching recommendations.
          </p>
          <Button variant="secondary" size="sm" onClick={() => refetchRecommendations()}>
            Try Again
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 max-w-6xl mx-auto">
      {/* Page Header - Responsive */}
      <div className="flex flex-col gap-4 mb-6">
        {/* Title Row */}
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 flex items-center gap-2">
            <DollarSign className="h-5 w-5 sm:h-6 sm:w-6 text-green-600" />
            Price Recommendations
            <AIBadge />
          </h1>
          <p className="text-sm sm:text-base text-gray-600 mt-1">
            Review and approve AI-generated pricing suggestions
          </p>
        </div>

        {/* Actions Row - Wraps on mobile */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => refetchRecommendations()}
            disabled={isLoading}
          >
            <RefreshCw className={`h-4 w-4 mr-1.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={handleGenerateRecommendations}
            disabled={isGenerating}
          >
            <Sparkles className={`h-4 w-4 mr-1.5 ${isGenerating ? 'animate-pulse' : ''}`} />
            {isGenerating ? 'Generating...' : 'Generate Recommendations'}
          </Button>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => router.push('/pricing/rules')}
          >
            <Settings className="h-4 w-4 mr-1.5" />
            Pricing Rules
          </Button>
        </div>
      </div>

      {/* Stats - Responsive grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6">
        <StatCard
          label="Pending Review"
          value={stats?.total_pending ?? 0}
          highlight
        />
        <StatCard
          label="Applied"
          value={stats?.total_applied ?? 0}
        />
        <StatCard
          label="Approval Rate"
          value={stats?.approval_rate ? `${Math.round(stats.approval_rate)}%` : '—'}
        />
        <StatCard
          label="Avg Confidence"
          value={stats?.avg_confidence ? `${Math.round(stats.avg_confidence * 100)}%` : '—'}
        />
      </div>

      {/* Info banner when no recommendations */}
      {!isLoading && (!recommendationsData?.items || recommendationsData.items.length === 0) && (
        <Card padding="md" className="mb-6 bg-blue-50 border-blue-200">
          <h3 className="text-blue-800 font-medium mb-2">No Recommendations Yet</h3>
          <p className="text-blue-700 text-sm mb-3">
            To generate recommendations, make sure you have:
          </p>
          <ul className="text-blue-700 text-sm list-disc list-inside mb-4 space-y-1">
            <li>At least one <strong>active pricing rule</strong> configured</li>
            <li>Competitor products linked with current prices</li>
            <li>Price differences that match your rule conditions</li>
          </ul>
          <Button
            variant="primary"
            size="sm"
            onClick={handleGenerateRecommendations}
            disabled={isGenerating}
          >
            <Sparkles className="h-4 w-4 mr-2" />
            {isGenerating ? 'Generating...' : 'Generate Recommendations Now'}
          </Button>
        </Card>
      )}

      {/* Recommendations List */}
      {isLoading ? (
        <RecommendationsListSkeleton count={3} />
      ) : (
        <RecommendationsList
          recommendations={recommendationsData?.items ?? []}
          productNames={productNames}
          productSkus={productSkus}
          filterStatus={filterStatus}
          onFilterChange={handleFilterChange}
          onApprove={handleApprove}
          onReject={handleReject}
          onView={handleView}
          actionLoadingId={actionLoadingId}
          showFilters
        />
      )}
    </div>
  );
}

