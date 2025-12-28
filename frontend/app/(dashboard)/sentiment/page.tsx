'use client';

import { useState, useMemo } from 'react';
import { SectionHeader, Card, Button } from '@/components/ui';
import { AIBadge } from '@/components/ui/ai-badge';
import {
  KpiCard,
  PeriodSelector,
  ProductSelector,
  PlatformSelector,
  SentimentChart,
  MentionVolumeChart,
  MentionCard,
  EmptyState,
  AnalyzeModal,
  SentimentBreakdown,
  TopKeywords,
  type Platform,
} from '@/components/features/sentiment';
import { useSentimentTrend, useDashboardOverview } from '@/lib/hooks';
import { useProducts, useMentions } from '@/lib/hooks';

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined) return '—';
  return (score * 100).toFixed(0);
}

function getSentimentLabel(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'No data';
  if (score >= 0.5) return 'Positive';
  if (score >= 0) return 'Neutral';
  return 'Negative';
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────

export default function SentimentPage() {
  const [days, setDays] = useState(30);
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [selectedPlatform, setSelectedPlatform] = useState<Platform>('all');
  const [analyzeModalOpen, setAnalyzeModalOpen] = useState(false);

  // Fetch products for dropdown
  const { data: productsData, isLoading: productsLoading } = useProducts({
    page: 1,
    page_size: 100,
  });

  // Fetch sentiment trend data
  const {
    data: trendData,
    isLoading: trendLoading,
    error: trendError,
  } = useSentimentTrend({
    days,
    bucket: 'day',
    product_id: selectedProductId || undefined,
  });

  // Fetch mentions for selected product
  const { data: mentionsData, isLoading: mentionsLoading } = useMentions(
    selectedProductId,
    { page: 1, page_size: 100 }
  );

  // Fetch dashboard overview
  const { data: dashboardData } = useDashboardOverview();

  // Get selected product name
  const selectedProduct = productsData?.items.find((p) => p.id === selectedProductId);

  // Filter mentions by platform
  const filteredMentions = useMemo(() => {
    if (!mentionsData?.items) return [];
    if (selectedPlatform === 'all') return mentionsData.items;
    return mentionsData.items.filter(
      (m) => m.source.toLowerCase() === selectedPlatform.toLowerCase()
    );
  }, [mentionsData, selectedPlatform]);

  // Chart data - pass raw timeline to charts (they format internally)
  const chartData = trendData?.timeline || [];
  const totalMentions = chartData.reduce((sum, d) => sum + d.mention_count, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <SectionHeader
          title={<span className="flex items-center gap-2">Sentiment Analysis <AIBadge /></span>}
          description={
            selectedProduct
              ? `Showing data for ${selectedProduct.name}`
              : 'Track social media sentiment for your products'
          }
        />
        <div className="flex flex-wrap items-center gap-3">
          <ProductSelector
            value={selectedProductId}
            onChange={setSelectedProductId}
            products={productsData?.items || []}
            isLoading={productsLoading}
          />
          <PeriodSelector value={days} onChange={setDays} />
          <Button onClick={() => setAnalyzeModalOpen(true)}>+ Analyze Text</Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KpiCard
          title="Current Sentiment"
          value={formatScore(trendData?.current_score)}
          subtitle={getSentimentLabel(trendData?.current_score)}
          trend={trendData?.trend}
          change={trendData?.change}
        />
        <KpiCard
          title="Previous Period"
          value={formatScore(trendData?.previous_score)}
          subtitle={getSentimentLabel(trendData?.previous_score)}
        />
        <KpiCard
          title="Total Mentions"
          value={totalMentions}
          subtitle={`Last ${days} days`}
        />
        <KpiCard
          title="Mentions (24h)"
          value={dashboardData?.total_mentions_24h ?? 0}
          subtitle="Today (all products)"
        />
      </div>

      {/* Loading state */}
      {trendLoading && (
        <Card className="p-8">
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          </div>
        </Card>
      )}

      {/* Error state */}
      {trendError && (
        <Card className="p-8">
          <div className="flex items-center justify-center h-64 text-red-500">
            Failed to load sentiment data:{' '}
            {trendError instanceof Error ? trendError.message : 'Unknown error'}
          </div>
        </Card>
      )}

      {/* Charts */}
      {!trendLoading && !trendError && chartData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <SentimentChart data={chartData} />
          <MentionVolumeChart data={chartData} />
        </div>
      )}

      {/* Empty chart state */}
      {!trendLoading && !trendError && chartData.length === 0 && (
        <EmptyState
          title="No sentiment data yet"
          description={
            selectedProductId
              ? 'No sentiment data for this product yet'
              : 'Sentiment data will appear here once you start analyzing content'
          }
        />
      )}

      {/* Sentiment Breakdown & Keywords - shown when product selected */}
      {selectedProductId && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="p-6">
            <h3 className="text-lg font-medium mb-4">Sentiment Breakdown</h3>
            {mentionsLoading ? (
              <div className="flex items-center justify-center h-48">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
              </div>
            ) : (
              <SentimentBreakdown mentions={mentionsData?.items || []} />
            )}
          </Card>

          <Card className="p-6">
            <h3 className="text-lg font-medium mb-4">Top Keywords</h3>
            {mentionsLoading ? (
              <div className="flex items-center justify-center h-24">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
              </div>
            ) : (
              <TopKeywords mentions={mentionsData?.items || []} />
            )}
          </Card>
        </div>
      )}

      {/* Mentions Feed */}
      {selectedProductId && (
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium">Recent Mentions</h3>
            <div className="flex items-center gap-3">
              <PlatformSelector value={selectedPlatform} onChange={setSelectedPlatform} />
              {mentionsData && mentionsData.total > 0 && (
                <span className="text-sm text-gray-500">
                  {filteredMentions.length} of {mentionsData.total} mention
                  {mentionsData.total !== 1 ? 's' : ''}
                </span>
              )}
            </div>
          </div>

          {mentionsLoading && (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
            </div>
          )}

          {!mentionsLoading && filteredMentions.length > 0 && (
            <div className="space-y-3">
              {filteredMentions.slice(0, 20).map((mention) => (
                <MentionCard key={mention.id} mention={mention} />
              ))}
            </div>
          )}

          {!mentionsLoading && filteredMentions.length === 0 && (
            <div className="flex flex-col items-center justify-center h-32 text-gray-500">
              <p className="text-sm">
                {selectedPlatform === 'all'
                  ? 'No mentions found for this product'
                  : `No ${selectedPlatform} mentions found`}
              </p>
              {selectedPlatform !== 'all' && (
                <p className="text-xs mt-1">Try selecting &quot;All Platforms&quot;</p>
              )}
            </div>
          )}
        </Card>
      )}

      {/* Prompt to select product */}
      {!selectedProductId && (
        <Card className="p-6">
          <div className="flex flex-col items-center justify-center h-32 text-gray-500">
            <svg className="w-8 h-8 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
            <p className="text-sm font-medium">Select a product to view detailed analysis</p>
            <p className="text-xs mt-1">Choose a product to see sentiment breakdown, keywords, and mentions</p>
          </div>
        </Card>
      )}

      {/* Analyze Modal */}
      <AnalyzeModal
        isOpen={analyzeModalOpen}
        onClose={() => setAnalyzeModalOpen(false)}
        defaultProductId={selectedProductId}
      />
    </div>
  );
}
