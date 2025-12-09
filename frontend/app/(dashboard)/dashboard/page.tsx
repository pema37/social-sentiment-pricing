// Dashboard Page
// Main overview page with stats, alerts, and product summaries

'use client';

import { Card, CardTitle, SectionHeader } from '@/components/ui';
import { Button } from '@/components/ui/Button';
import {
  Package,
  DollarSign,
  Users,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  CheckCircle,
  Bell,
  RefreshCw,
  Info,
  ArrowUpRight,
  ArrowDownRight,
  Eye,
} from 'lucide-react';
import Link from 'next/link';
import {
  useDashboardOverview,
  useProductSummaries,
  useAlerts,
  useRefreshDashboard,
} from '@/lib/hooks/use-analytics';
import type { Alert, ProductSummary } from '@/lib/api/client';

// =============================================================================
// COMPONENTS
// =============================================================================

function StatCard({ 
  title, 
  value, 
  subtitle,
  trend,
  icon: Icon,
  iconBgColor = 'bg-blue-50',
  iconColor = 'text-blue-600',
  isLoading,
}: { 
  title: string; 
  value: string; 
  subtitle?: string;
  trend?: 'up' | 'down' | 'neutral';
  icon: React.ElementType;
  iconBgColor?: string;
  iconColor?: string;
  isLoading?: boolean;
}) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm text-gray-500">{title}</p>
          {isLoading ? (
            <div className="h-8 w-20 bg-gray-200 rounded animate-pulse mt-1" />
          ) : (
            <p className="text-2xl font-semibold text-gray-900 mt-1">{value}</p>
          )}
          {subtitle && (
            <div className="flex items-center gap-1 mt-1">
              {trend === 'up' && <ArrowUpRight className="w-4 h-4 text-green-500" />}
              {trend === 'down' && <ArrowDownRight className="w-4 h-4 text-red-500" />}
              {isLoading ? (
                <div className="h-4 w-24 bg-gray-100 rounded animate-pulse" />
              ) : (
                <p className={`text-sm ${
                  trend === 'up' ? 'text-green-600' : 
                  trend === 'down' ? 'text-red-600' : 'text-gray-500'
                }`}>
                  {subtitle}
                </p>
              )}
            </div>
          )}
        </div>
        <div className={`p-3 rounded-xl ${iconBgColor}`}>
          <Icon className={`w-6 h-6 ${iconColor}`} />
        </div>
      </div>
    </Card>
  );
}

function SentimentIndicator({ 
  trend, 
  score 
}: { 
  trend: 'improving' | 'declining' | 'stable'; 
  score: number | null;
}) {
  const icons = {
    improving: TrendingUp,
    declining: TrendingDown,
    stable: Minus,
  };
  const colors = {
    improving: 'text-green-500',
    declining: 'text-red-500',
    stable: 'text-gray-500',
  };
  const labels = {
    improving: 'Improving',
    declining: 'Declining',
    stable: 'Stable',
  };
  
  const Icon = icons[trend];
  
  return (
    <div className="flex items-center gap-2">
      <Icon className={`w-5 h-5 ${colors[trend]}`} />
      <span className="text-sm text-gray-600">{labels[trend]}</span>
      {score !== null && (
        <span className={`text-sm font-medium ${score >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          ({score >= 0 ? '+' : ''}{score.toFixed(2)})
        </span>
      )}
    </div>
  );
}

function AlertItem({ alert }: { alert: Alert }) {
  const severityStyles = {
    critical: { bg: 'bg-red-50', border: 'border-red-200', icon: AlertTriangle, iconColor: 'text-red-500' },
    high: { bg: 'bg-orange-50', border: 'border-orange-200', icon: AlertTriangle, iconColor: 'text-orange-500' },
    medium: { bg: 'bg-amber-50', border: 'border-amber-200', icon: Bell, iconColor: 'text-amber-500' },
    low: { bg: 'bg-blue-50', border: 'border-blue-200', icon: Info, iconColor: 'text-blue-500' },
  };
  
  const style = severityStyles[alert.severity] || severityStyles.low;
  const IconComponent = style.icon;
  const timeAgo = formatTimeAgo(alert.created_at);

  return (
    <div className={`p-3 rounded-lg border ${style.bg} ${style.border}`}>
      <div className="flex items-start gap-3">
        <IconComponent className={`w-5 h-5 ${style.iconColor} mt-0.5 shrink-0`} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{alert.title}</p>
          <p className="text-sm text-gray-600 mt-0.5 line-clamp-2">{alert.message}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              alert.status === 'pending' ? 'bg-yellow-100 text-yellow-700' :
              alert.status === 'acknowledged' ? 'bg-blue-100 text-blue-700' :
              'bg-green-100 text-green-700'
            }`}>
              {alert.status}
            </span>
            <span className="text-xs text-gray-400">{timeAgo}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ProductCard({ product }: { product: ProductSummary }) {
  const priceChangeColor = product.price_change_percent > 0 
    ? 'text-green-600' 
    : product.price_change_percent < 0 
    ? 'text-red-600' 
    : 'text-gray-500';

  return (
    <div className="p-4 border border-gray-200 rounded-lg hover:border-gray-300 transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900 truncate">{product.name}</h3>
          {product.sku && (
            <p className="text-xs text-gray-500 mt-0.5">SKU: {product.sku}</p>
          )}
        </div>
        {product.auto_pricing_enabled && (
          <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full">
            Auto
          </span>
        )}
      </div>
      
      <div className="mt-3 flex items-end justify-between">
        <div>
          <p className="text-lg font-semibold text-gray-900">
            ${parseFloat(product.current_price).toFixed(2)}
          </p>
          <p className={`text-sm ${priceChangeColor}`}>
            {product.price_change_percent > 0 ? '+' : ''}
            {product.price_change_percent.toFixed(1)}% from base
          </p>
        </div>
        <div className="text-right">
          {product.sentiment_score !== null && (
            <p className={`text-sm font-medium ${
              product.sentiment_score >= 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {product.sentiment_score >= 0 ? '+' : ''}{product.sentiment_score.toFixed(2)}
            </p>
          )}
          <p className="text-xs text-gray-500">
            {product.mention_count_24h} mentions
          </p>
        </div>
      </div>
      
      {product.has_pending_recommendation && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <span className="text-xs text-amber-600 flex items-center gap-1">
            <Bell className="w-3 h-3" />
            Pending recommendation
          </span>
        </div>
      )}
    </div>
  );
}

function LoadingList({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="h-20 bg-gray-100 rounded-lg animate-pulse" />
      ))}
    </div>
  );
}

function EmptyState({ message, icon: Icon = Info }: { message: string; icon?: React.ElementType }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-gray-500">
      <Icon className="w-8 h-8 mb-2 text-gray-400" />
      <p className="text-sm">{message}</p>
    </div>
  );
}

// Helper function to format time ago
function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return date.toLocaleDateString();
}

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
  
  const { 
    data: products, 
    isLoading: productsLoading,
  } = useProductSummaries(6);
  
  const { 
    data: alertsData, 
    isLoading: alertsLoading,
  } = useAlerts({ limit: 5, status: 'pending' });

  const isRefreshing = overviewFetching;

  const handleRefresh = () => {
    refreshDashboard();
  };

  // Extract alerts from paginated response
  const alerts = alertsData?.items || [];

  return (
    <div>
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
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          title="Products Tracked"
          value={overview?.total_products?.toString() || '0'}
          subtitle={overview ? `${overview.products_with_auto_pricing} with auto-pricing` : undefined}
          icon={Package}
          iconBgColor="bg-blue-50"
          iconColor="text-blue-600"
          isLoading={overviewLoading}
        />
        <StatCard
          title="Pending Recommendations"
          value={overview?.pending_recommendations?.toString() || '0'}
          subtitle={overview ? `${overview.applied_recommendations_7d} applied this week` : undefined}
          trend={overview && overview.pending_recommendations > 0 ? 'up' : 'neutral'}
          icon={DollarSign}
          iconBgColor="bg-green-50"
          iconColor="text-green-600"
          isLoading={overviewLoading}
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
        />
        <StatCard
          title="Competitors"
          value={overview?.total_competitors?.toString() || '0'}
          subtitle={overview ? `${overview.total_mentions_24h} mentions (24h)` : undefined}
          icon={Users}
          iconBgColor="bg-purple-50"
          iconColor="text-purple-600"
          isLoading={overviewLoading}
        />
      </div>

      {/* Sentiment Overview Card */}
      {overview && (
        <Card className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Overall Sentiment</CardTitle>
              <div className="mt-2">
                <SentimentIndicator 
                  trend={overview.sentiment_trend} 
                  score={overview.average_sentiment} 
                />
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">24h Mentions</p>
              <p className="text-2xl font-semibold text-gray-900">
                {overview.total_mentions_24h.toLocaleString()}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Main content grid */}
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
                <LoadingList count={3} />
                <LoadingList count={3} />
              </div>
            ) : products && products.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {products.map((product) => (
                  <ProductCard key={product.id} product={product} />
                ))}
              </div>
            ) : (
              <EmptyState 
                message="No products yet. Add your first product to get started." 
                icon={Package}
              />
            )}
          </Card>
        </div>

        {/* Alerts section - takes 1 column */}
        <div>
          <Card>
            <div className="flex items-center justify-between mb-4">
              <CardTitle>Pending Alerts</CardTitle>
              <Link href="/alerts">
                <Button variant="ghost" size="sm">View All</Button>
              </Link>
            </div>
            
            {alertsLoading ? (
              <LoadingList count={3} />
            ) : alerts.length > 0 ? (
              <div className="space-y-3">
                {alerts.map((alert) => (
                  <AlertItem key={alert.id} alert={alert} />
                ))}
              </div>
            ) : (
              <EmptyState 
                message="No pending alerts" 
                icon={CheckCircle}
              />
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
