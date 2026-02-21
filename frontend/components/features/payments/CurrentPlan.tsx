// frontend/components/features/payments/CurrentPlan.tsx

'use client';

import { CreditCard, Calendar, CheckCircle2, AlertCircle } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { useSubscription } from '@/lib/hooks/use-payments';

export function CurrentPlan() {
  const { data: subscription, isLoading } = useSubscription();

  if (isLoading) {
    return (
      <Card className="p-6 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
        <div className="h-16 bg-gray-200 rounded"></div>
      </Card>
    );
  }

  if (!subscription) {
    return null;
  }

  const isActive = subscription.status === 'active';

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getStatusBadge = () => {
    const baseClasses = 'px-2 py-1 text-xs font-medium rounded-full';
    switch (subscription.status) {
      case 'active':
        return <span className={`${baseClasses} bg-green-100 text-green-800`}>Active</span>;
      case 'past_due':
        return <span className={`${baseClasses} bg-yellow-100 text-yellow-800`}>Past Due</span>;
      case 'cancelled':
        return <span className={`${baseClasses} bg-red-100 text-red-800`}>Cancelled</span>;
      case 'trialing':
        return <span className={`${baseClasses} bg-blue-100 text-blue-800`}>Trialing</span>;
      default:
        return <span className={`${baseClasses} bg-gray-100 text-gray-800`}>Inactive</span>;
    }
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <CreditCard className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-semibold">Current Subscription</h3>
        </div>
        {getStatusBadge()}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Plan Info */}
        <div className="bg-gray-50 rounded-lg p-4">
          <span className="text-sm text-gray-500">Plan</span>
          <p className="text-2xl font-bold">{subscription.name}</p>
          <p className="text-lg text-gray-600">
            ${subscription.monthly_price}/month
          </p>
        </div>

        {/* Usage Limits */}
        <div className="bg-gray-50 rounded-lg p-4">
          <span className="text-sm text-gray-500">Limits</span>
          <div className="space-y-1 mt-2">
            <div className="flex justify-between text-sm">
              <span>Products:</span>
              <span className="font-medium">
                {subscription.limits.products === -1
                  ? 'Unlimited'
                  : subscription.limits.products}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span>Competitors:</span>
              <span className="font-medium">
                {subscription.limits.competitors === -1
                  ? 'Unlimited'
                  : subscription.limits.competitors}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span>API Calls:</span>
              <span className="font-medium">
                {subscription.limits.api_calls === -1
                  ? 'Unlimited'
                  : subscription.limits.api_calls.toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        {/* Billing Period */}
        <div className="bg-gray-50 rounded-lg p-4">
          <span className="text-sm text-gray-500">Billing Period</span>
          {subscription.current_period_start ? (
            <div className="mt-2 space-y-1">
              <div className="flex items-center gap-2 text-sm">
                <Calendar className="h-4 w-4 text-gray-400" />
                <span>
                  {formatDate(subscription.current_period_start)} -{' '}
                  {formatDate(subscription.current_period_end)}
                </span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500 mt-2">
              {subscription.tier === 'free'
                ? 'Free plan - no billing'
                : 'No active billing period'}
            </p>
          )}
        </div>
      </div>

      {/* Features */}
      <div className="mt-6 border-t pt-4">
        <span className="text-sm text-gray-500 font-medium">Included Features</span>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-2">
          {subscription.features.map((feature, index) => (
            <div key={index} className="flex items-center gap-2 text-sm">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              <span>{feature}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Warnings */}
      {subscription.status === 'past_due' && (
        <div className="mt-4 bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-yellow-600 shrink-0" />
          <div>
            <p className="font-medium text-yellow-800">Payment Past Due</p>
            <p className="text-sm text-yellow-700">
              Your subscription payment is overdue. Please update your payment to
              continue accessing premium features.
            </p>
          </div>
        </div>
      )}

      {subscription.status === 'cancelled' && (
        <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-600 shrink-0" />
          <div>
            <p className="font-medium text-red-800">Subscription Cancelled</p>
            <p className="text-sm text-red-700">
              Your subscription has been cancelled. You can resubscribe at any time.
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
