// Dashboard Page
// Main overview page with stats, alerts, and product summaries

'use client';

import Link from 'next/link';
import { Package, DollarSign, Users, Bell, RefreshCw, Eye } from 'lucide-react';
import { Card, CardTitle, SectionHeader } from '@/components/ui';
import { Button } from '@/components/ui/Button';
import {
  StatCard,
  RecentAlerts,
  ProductSummaryCard,
  SentimentOverview,
  QuickActions,
  PendingRecommendations,
  AIFeaturesCard,
} from '@/components/features/dashboard';
import {
  useDashboardOverview,
  useProductSummaries,
  useRefreshDashboard,
} from '@/lib/hooks/use-analytics';
import { useAlerts } from '@/lib/hooks/use-alerts';
import { useRecommendations } from '@/lib/hooks/use-pricing';

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function DashboardPage() {
  const refreshDashboard = useRefreshDashboard();

  // Fetch data with React Query hooks
  const {
    data: overview,
    isLoading: overviewLoading,
    isFetching: overviewFetching,
  } = useDashboardOverview();

  const { data: products, isLoading: productsLoading } = useProductSummaries(6);

  const { data: alertsData, isLoading: alertsLoading } = useAlerts({
    limit: 5,
    status: 'pending',
  });

  const { data: recommendationsData, isLoading: recommendationsLoading } = useRecommendations({
    status: 'pending',
    page_size: 5,
  });

  const isRefreshing = overviewFetching;

  const handleRefresh = () => {
    refreshDashboard.refresh();
  };

  // Extract data from paginated responses
  const alerts = alertsData?.items || [];
  const recommendations = recommendationsData?.items || [];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <SectionHeader
        title="Dashboard"
        description="Monitor your pricing and sentiment analytics"
        action={
          <Button
            variant="secondary"
            size="sm"
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        }
      />

      {/* Stats grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Products Tracked"
          value={overview?.total_products?.toString() || '0'}
          subtitle={
            overview ? `${overview.products_with_auto_pricing} with auto-pricing` : undefined
          }
          icon={Package}
          iconBgColor="bg-blue-50"
          iconColor="text-blue-600"
          isLoading={overviewLoading}
          href="/products"
        />
        <StatCard
          title="Pending Recommendations"
          value={overview?.pending_recommendations?.toString() || '0'}
          subtitle={
            overview ? `${overview.applied_recommendations_7d} applied this week` : undefined
          }
          trend={overview && overview.pending_recommendations > 0 ? 'up' : 'neutral'}
          icon={DollarSign}
          iconBgColor="bg-green-50"
          iconColor="text-green-600"
          isLoading={overviewLoading}
          href="/pricing"
        />
        <StatCard
          title="Active Alerts"
          value={overview?.unread_alerts?.toString() || '0'}
          subtitle={overview ? `${overview.alerts_today} new today` : undefined}
          trend={overview && overview.unread_alerts > 5 ? 'up' : 'neutral'}
          icon={Bell}
          iconBgColor="bg-amber-50"
          iconColor="text-amber-600"
          isLoading={overviewLoading}
          href="/alerts"
        />
        <StatCard
          title="Competitors"
          value={overview?.total_competitors?.toString() || '0'}
          subtitle={overview ? `${overview.total_mentions_24h} mentions (24h)` : undefined}
          icon={Users}
          iconBgColor="bg-purple-50"
          iconColor="text-purple-600"
          isLoading={overviewLoading}
          href="/competitors"
        />
      </div>

      {/* AI Features Showcase */}
      <AIFeaturesCard />

      {/* Sentiment Overview */}
      <SentimentOverview
        trend={overview?.sentiment_trend || 'stable'}
        score={overview?.average_sentiment ?? null}
        mentions24h={overview?.total_mentions_24h || 0}
        isLoading={overviewLoading}
      />

      {/* Quick Actions */}
      <Card>
        <CardTitle className="mb-4">Quick Actions</CardTitle>
        <QuickActions maxItems={6} />
      </Card>

      {/* Main content grid - 3 columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Products section - takes 2 columns */}
        <div className="lg:col-span-2">
          <Card>
            <div className="flex items-center justify-between mb-4">
              <CardTitle>Top Products</CardTitle>
              <Link href="/products">
                <Button variant="ghost" size="sm">
                  <Eye className="w-4 h-4 mr-1" />
                  View All
                </Button>
              </Link>
            </div>

            {productsLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="h-32 bg-gray-100 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : products && products.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {products.map((product) => (
                  <ProductSummaryCard key={product.id} product={product} />
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-gray-500">
                <Package className="w-8 h-8 mb-2 text-gray-400" />
                <p className="text-sm">No products yet. Add your first product to get started.</p>
              </div>
            )}
          </Card>
        </div>

        {/* Right column - Alerts & Recommendations */}
        <div className="space-y-6">
          {/* Pending Alerts */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <CardTitle>Pending Alerts</CardTitle>
              <Link href="/alerts">
                <Button variant="ghost" size="sm">
                  View All
                </Button>
              </Link>
            </div>
            <RecentAlerts alerts={alerts} isLoading={alertsLoading} maxItems={5} />
          </Card>

          {/* Pending Recommendations */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <CardTitle>Price Recommendations</CardTitle>
              <Link href="/pricing">
                <Button variant="ghost" size="sm">
                  View All
                </Button>
              </Link>
            </div>
            <PendingRecommendations
              recommendations={recommendations}
              isLoading={recommendationsLoading}
              maxItems={5}
            />
          </Card>
        </div>
      </div>
    </div>
  );
}

