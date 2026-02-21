// frontend/app/(dashboard)/settings/billing/page.tsx
'use client';

import { Card, CardTitle } from '@/components/ui';
import { Button } from '@/components/ui/Button';
import { 
  CreditCard, 
  Check, 
  Zap, 
  Building2, 
  ExternalLink,
  Receipt,
  Calendar,
  RefreshCw,
  Star,
} from 'lucide-react';
import { useSubscription, usePlans, paymentKeys } from '@/lib/hooks/use-payments';
import { useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import type { SubscriptionTier, PlansResponse } from '@/types/payment';

// Plan display configuration
const PLAN_CONFIG: Record<SubscriptionTier, { 
  icon: React.ReactNode; 
  popular?: boolean;
  description: string;
}> = {
  free: {
    icon: <Zap className="w-5 h-5 text-gray-500" />,
    description: 'Basic features for getting started',
  },
  starter: {
    icon: <Zap className="w-5 h-5 text-blue-500" />,
    description: 'For small businesses',
  },
  professional: {
    icon: <Star className="w-5 h-5 text-purple-500" />,
    popular: true,
    description: 'For growing businesses',
  },
  enterprise: {
    icon: <Building2 className="w-5 h-5 text-orange-500" />,
    description: 'For large organizations',
  },
};

export default function BillingSettingsPage() {
  const queryClient = useQueryClient();
  const { data: subscription, isLoading: subLoading, isRefetching } = useSubscription();
  const { data: plansData, isLoading: plansLoading } = usePlans();

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: paymentKeys.subscription() });
  };

  const isLoading = subLoading || plansLoading;

  // Get current tier from subscription
  const currentTier: SubscriptionTier = subscription?.tier || 'free';
  const isActive = subscription?.status === 'active';

  // Extract plans array from PlansResponse
  const plans = (plansData as PlansResponse)?.plans || [];

  // Format dates
  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return null;
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  // Format price display
  const formatPrice = (price: string | undefined | null) => {
    if (!price) return '$0';
    const numPrice = parseFloat(price);
    if (isNaN(numPrice) || numPrice === 0) return '$0';
    return `$${numPrice.toFixed(2).replace(/\.00$/, '')}`;
  };

  // Get current price as number for comparison
  const currentPriceNum = subscription?.monthly_price 
    ? parseFloat(subscription.monthly_price) 
    : 0;

  return (
    <div className="space-y-6">
      {/* Current Plan */}
      <Card>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>Current Plan</CardTitle>
            {isLoading ? (
              <div className="h-4 bg-gray-200 rounded w-48 mt-2 animate-pulse" />
            ) : (
              <p className="text-sm text-gray-500 mt-1">
                You are currently on the <span className="font-medium capitalize">{currentTier}</span> plan
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              disabled={isRefetching}
              className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
              title="Refresh subscription status"
            >
              <RefreshCw className={`w-4 h-4 ${isRefetching ? 'animate-spin' : ''}`} />
            </button>
            {isActive && (
              <span className="px-3 py-1 bg-green-100 text-green-700 text-sm font-medium rounded-full">
                Active
              </span>
            )}
            {subscription?.status === 'past_due' && (
              <span className="px-3 py-1 bg-yellow-100 text-yellow-700 text-sm font-medium rounded-full">
                Past Due
              </span>
            )}
            {subscription?.status === 'cancelled' && (
              <span className="px-3 py-1 bg-red-100 text-red-700 text-sm font-medium rounded-full">
                Cancelled
              </span>
            )}
          </div>
        </div>

        {isLoading ? (
          <div className="mt-6 p-4 bg-gray-50 rounded-lg animate-pulse">
            <div className="h-16 bg-gray-200 rounded" />
          </div>
        ) : (
          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-white rounded-lg border border-gray-200">
                  {PLAN_CONFIG[currentTier]?.icon || <Zap className="w-5 h-5 text-blue-600" />}
                </div>
                <div>
                  <p className="font-medium text-gray-900 capitalize">{subscription?.name || currentTier} Plan</p>
                  <p className="text-sm text-gray-500">
                    {PLAN_CONFIG[currentTier]?.description || 'Your current subscription'}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-2xl font-semibold text-gray-900">
                  {formatPrice(subscription?.monthly_price)}
                </p>
                <p className="text-sm text-gray-500">
                  {currentTier === 'free' ? 'forever' : '/month'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Plan limits */}
        {subscription?.limits && (
          <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-gray-500">Products</p>
              <p className="font-semibold text-gray-900">
                {subscription.limits.products === -1 ? 'Unlimited' : subscription.limits.products}
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-gray-500">Competitors</p>
              <p className="font-semibold text-gray-900">
                {subscription.limits.competitors === -1 ? 'Unlimited' : subscription.limits.competitors}
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-gray-500">API Calls</p>
              <p className="font-semibold text-gray-900">
                {subscription.limits.api_calls === -1 ? 'Unlimited' : subscription.limits.api_calls.toLocaleString()}
              </p>
            </div>
          </div>
        )}

        {/* Features list */}
        {subscription?.features && subscription.features.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <p className="text-sm font-medium text-gray-700 mb-2">Included Features</p>
            <div className="flex flex-wrap gap-2">
              {subscription.features.map((feature) => (
                <span 
                  key={feature} 
                  className="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 text-xs rounded-full"
                >
                  <Check className="w-3 h-3" />
                  {feature}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="mt-4 flex items-center gap-4 text-sm text-gray-500">
          {subscription?.current_period_end ? (
            <div className="flex items-center gap-1">
              <Calendar className="w-4 h-4" />
              <span>Renews {formatDate(subscription.current_period_end)}</span>
            </div>
          ) : (
            <div className="flex items-center gap-1">
              <Calendar className="w-4 h-4" />
              <span>No renewal date</span>
            </div>
          )}
        </div>
      </Card>

      {/* Available Plans */}
      <Card>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Available Plans</CardTitle>
            <p className="text-sm text-gray-500 mt-1">
              Upgrade to unlock more features
            </p>
          </div>
          <Link href="/payments">
            <Button variant="secondary" size="sm">
              <CreditCard className="w-4 h-4 mr-1" />
              Manage Payments
            </Button>
          </Link>
        </div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {plans.map((plan) => {
            // plan.id is the SubscriptionTier
            const planTier = plan.id;
            const config = PLAN_CONFIG[planTier];
            const isCurrent = planTier === currentTier;
            const planPriceNum = parseFloat(plan.monthly_price) || 0;
            
            return (
              <div
                key={planTier}
                className={`relative p-4 rounded-lg border-2 transition-colors ${
                  isCurrent
                    ? 'border-blue-500 bg-blue-50/50'
                    : config?.popular
                    ? 'border-purple-200 hover:border-purple-300'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                {config?.popular && !isCurrent && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-purple-600 text-white text-xs font-medium rounded-full whitespace-nowrap">
                    Most Popular
                  </span>
                )}
                {isCurrent && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-blue-600 text-white text-xs font-medium rounded-full whitespace-nowrap">
                    Current Plan
                  </span>
                )}
                
                <div className="text-center mb-4">
                  <div className="flex justify-center mb-2">
                    {config?.icon || <Zap className="w-5 h-5 text-gray-500" />}
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900">
                    {plan.name}
                  </h3>
                  <div className="mt-1">
                    <span className="text-2xl font-bold text-gray-900">
                      {formatPrice(plan.monthly_price)}
                    </span>
                    <span className="text-sm text-gray-500">
                      {planTier === 'free' ? '/forever' : '/month'}
                    </span>
                  </div>
                  {planTier !== 'free' && (
                    <p className="text-xs text-gray-500 mt-1">
                      Paid in MNEE (1 MNEE = $1 USD)
                    </p>
                  )}
                </div>

                {/* Plan limits */}
                <div className="space-y-1 mb-4 text-sm text-gray-600">
                  <div className="flex justify-between">
                    <span>Products</span>
                    <span className="font-medium">
                      {plan.products_limit === -1 ? 'Unlimited' : plan.products_limit}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Competitors</span>
                    <span className="font-medium">
                      {plan.competitors_limit === -1 ? 'Unlimited' : plan.competitors_limit}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>API Calls</span>
                    <span className="font-medium">
                      {plan.api_calls_limit === -1 ? 'Unlimited' : plan.api_calls_limit.toLocaleString()}
                    </span>
                  </div>
                </div>

                {/* Features */}
                <ul className="space-y-2 mb-4">
                  {plan.features.slice(0, 4).map((feature) => (
                    <li key={feature} className="flex items-start gap-2 text-sm">
                      <Check className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
                      <span className="text-gray-600">{feature}</span>
                    </li>
                  ))}
                  {plan.features.length > 4 && (
                    <li className="text-xs text-gray-500 pl-6">
                      +{plan.features.length - 4} more features
                    </li>
                  )}
                </ul>

                {isCurrent ? (
                  <Button variant="secondary" size="sm" className="w-full" disabled>
                    Current Plan
                  </Button>
                ) : planTier === 'enterprise' ? (
                  <Button variant="secondary" size="sm" className="w-full">
                    <Building2 className="w-4 h-4 mr-1" />
                    Contact Sales
                  </Button>
                ) : (
                  <Link href="/payments" className="block">
                    <Button variant="primary" size="sm" className="w-full">
                      {planPriceNum > currentPriceNum ? 'Upgrade' : 'Switch'}
                    </Button>
                  </Link>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Payment Method - Link to Payments Page */}
      <Card>
        <CardTitle>Payment Method</CardTitle>
        <p className="text-sm text-gray-500 mt-1">
          Manage your payment information
        </p>

        <div className="mt-6 p-4 border border-dashed border-gray-300 rounded-lg text-center">
          <CreditCard className="w-8 h-8 text-gray-400 mx-auto mb-2" />
          <p className="text-sm text-gray-600">Payment via MNEE stablecoin</p>
          <p className="text-xs text-gray-500 mt-1">
            Connect your wallet on the Payments page to subscribe
          </p>
          <Link href="/payments">
            <Button variant="secondary" size="sm" className="mt-4">
              Go to Payments
            </Button>
          </Link>
        </div>
      </Card>

      {/* Billing History */}
      <Card>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Billing History</CardTitle>
            <p className="text-sm text-gray-500 mt-1">
              View your past invoices and receipts
            </p>
          </div>
          <Link href="/payments">
            <Button variant="ghost" size="sm">
              <ExternalLink className="w-4 h-4 mr-1" />
              View All
            </Button>
          </Link>
        </div>

        <div className="mt-6 flex flex-col items-center justify-center py-8 text-gray-500">
          <Receipt className="w-8 h-8 mb-2 text-gray-400" />
          <p className="text-sm">View payment history on the Payments page</p>
          <Link href="/payments" className="mt-2">
            <span className="text-xs text-blue-600 hover:underline">
              Go to Payments →
            </span>
          </Link>
        </div>
      </Card>
    </div>
  );
}




