// frontend/app/(dashboard)/settings/billing/page.tsx
'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Card, CardTitle } from '@/components/ui';
import { Button } from '@/components/ui/Button';
import {
  CreditCard,
  Check,
  Zap,
  Building2,
  Star,
  RefreshCw,
  Calendar,
  Receipt,
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  Loader2,
} from 'lucide-react';

// MNEE billing (existing)
import { useSubscription, usePlans, paymentKeys } from '@/lib/hooks/use-payments';
import { useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import type { SubscriptionTier, PlansResponse, ShopifyBillingTier } from '@/types/payment';
import { useShopifyEmbedded } from '@/lib/context/shopify-embedded';

// Shopify billing (new)
import {
  useShopifyPlans,
  useShopifyBillingStatus,
  useShopifySubscribe,
  useShopifyChangePlan,
  useShopifyCancelSubscription,
} from '@/lib/hooks/use-shopify-billing';
import { verifyShopifyCharge } from '@/lib/api/shopify-billing';
import type { ShopifyPlanInfo } from '@/lib/api/shopify-billing';

// =============================================================================
// PLAN DISPLAY CONFIG (shared)
// =============================================================================

const PLAN_CONFIG: Record<string, {
  icon: React.ReactNode;
  popular?: boolean;
  description: string;
}> = {
  free: {
    icon: <Sparkles className="w-5 h-5 text-gray-500" />,
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

// =============================================================================
// SHOPIFY BILLING UI
// =============================================================================

function ShopifyBillingPage({ shop }: { shop: string | null }) {
  const searchParams = useSearchParams();
  const chargeId = searchParams.get('charge_id');
  const justInstalled = searchParams.get('installed') === 'true';

  // Verification state
  const [verifyState, setVerifyState] = useState<{
    status: 'idle' | 'verifying' | 'approved' | 'declined' | 'error';
    tier: string | null;
    message: string | null;
  }>({ status: chargeId ? 'verifying' : 'idle', tier: null, message: null });

  const { data: plans, isLoading: plansLoading } = useShopifyPlans();
  const { data: status, isLoading: statusLoading, refetch: refetchStatus } = useShopifyBillingStatus(shop || undefined);
  const subscribeMutation = useShopifySubscribe();
  const changePlanMutation = useShopifyChangePlan();
  const cancelMutation = useShopifyCancelSubscription();

  // Verify charge_id on mount if present in URL
  useEffect(() => {
    if (!chargeId) return;

    let cancelled = false;

    async function verify() {
      try {
        const result = await verifyShopifyCharge({
          charge_id: chargeId!,
          shop_domain: shop,
        });

        if (cancelled) return;

        if (result.success) {
          setVerifyState({
            status: 'approved',
            tier: result.tier || null,
            message: result.message,
          });
          // Refresh billing status after successful verification
          refetchStatus();
        } else {
          setVerifyState({
            status: 'declined',
            tier: result.tier || null,
            message: result.message,
          });
        }
      } catch {
        if (cancelled) return;
        setVerifyState({
          status: 'error',
          tier: null,
          message: 'Failed to verify subscription. Please refresh the page.',
        });
      }
    }

    verify();

    return () => {
      cancelled = true;
    };
  }, [chargeId, shop, refetchStatus]);

  const isLoading = plansLoading || statusLoading;
  const currentTier = status?.tier || null;
  const hasActiveSub = status?.has_active_subscription || false;

  const handleSubscribe = (tier: ShopifyBillingTier) => {
    if (hasActiveSub) {
      changePlanMutation.mutate({ new_tier: tier, shop_domain: shop });
    } else {
      subscribeMutation.mutate({ tier, shop_domain: shop });
    }
  };

  const handleCancel = () => {
    if (confirm('Are you sure you want to cancel your subscription? You will be downgraded to the free plan.')) {
      cancelMutation.mutate({ prorate: true, shop_domain: shop });
    }
  };

  return (
    <div className="space-y-6">
      {/* Verification banners */}
      {verifyState.status === 'verifying' && (
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-3">
          <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
          <div>
            <p className="font-medium text-blue-800">Verifying subscription...</p>
            <p className="text-sm text-blue-700">
              Confirming your plan with Shopify. This takes a moment.
            </p>
          </div>
        </div>
      )}

      {verifyState.status === 'approved' && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5 text-green-600" />
          <div>
            <p className="font-medium text-green-800">Subscription Activated!</p>
            <p className="text-sm text-green-700">
              Your {verifyState.tier} plan is now active. Enjoy ActualPrice!
            </p>
          </div>
        </div>
      )}

      {verifyState.status === 'declined' && (
        <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-yellow-600" />
          <div>
            <p className="font-medium text-yellow-800">Subscription Not Approved</p>
            <p className="text-sm text-yellow-700">
              {verifyState.message || 'The charge was not approved. You can try again below.'}
            </p>
          </div>
        </div>
      )}

      {verifyState.status === 'error' && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-600" />
          <div>
            <p className="font-medium text-red-800">Verification Error</p>
            <p className="text-sm text-red-700">
              {verifyState.message || 'Something went wrong. Please refresh the page.'}
            </p>
          </div>
        </div>
      )}

      {justInstalled && verifyState.status === 'idle' && (
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-3">
          <Sparkles className="w-5 h-5 text-blue-600" />
          <div>
            <p className="font-medium text-blue-800">Welcome to ActualPrice!</p>
            <p className="text-sm text-blue-700">
              Choose a plan below to get started. All plans include a 14-day free trial.
            </p>
          </div>
        </div>
      )}

      {/* Current Shopify Plan */}
      <Card>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>Current Plan</CardTitle>
            {isLoading ? (
              <div className="h-4 bg-gray-200 rounded w-48 mt-2 animate-pulse" />
            ) : hasActiveSub ? (
              <p className="text-sm text-gray-500 mt-1">
                You are on the <span className="font-medium capitalize">{currentTier}</span> plan
                {status?.test && <span className="text-orange-500 ml-1">(test mode)</span>}
              </p>
            ) : (
              <p className="text-sm text-gray-500 mt-1">No active subscription</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => refetchStatus()}
              className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
              title="Refresh billing status"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            {hasActiveSub && (
              <span className="px-3 py-1 bg-green-100 text-green-700 text-sm font-medium rounded-full">
                Active
              </span>
            )}
          </div>
        </div>

        {hasActiveSub && (
          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-white rounded-lg border border-gray-200">
                  {PLAN_CONFIG[currentTier || 'starter']?.icon}
                </div>
                <div>
                  <p className="font-medium text-gray-900">{status?.plan_name || 'ActualPrice Plan'}</p>
                  <p className="text-sm text-gray-500">
                    {PLAN_CONFIG[currentTier || 'starter']?.description}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-2xl font-semibold text-gray-900">
                  ${status?.price || '0'}<span className="text-sm font-normal text-gray-500">/mo</span>
                </p>
                {status?.trial_days && status.trial_days > 0 && (
                  <p className="text-xs text-blue-600">{status.trial_days}-day trial</p>
                )}
              </div>
            </div>
          </div>
        )}

        {hasActiveSub && status?.current_period_end && (
          <div className="mt-4 flex items-center gap-4 text-sm text-gray-500">
            <div className="flex items-center gap-1">
              <Calendar className="w-4 h-4" />
              <span>
                Renews{' '}
                {new Date(status.current_period_end).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                })}
              </span>
            </div>
          </div>
        )}
      </Card>

      {/* Available Shopify Plans */}
      <Card>
        <div>
          <CardTitle>
            {hasActiveSub ? 'Change Plan' : 'Choose a Plan'}
          </CardTitle>
          <p className="text-sm text-gray-500 mt-1">
            {hasActiveSub
              ? 'Upgrade or downgrade your plan. Changes take effect immediately.'
              : 'All plans include a 14-day free trial. Cancel anytime.'}
          </p>
        </div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          {isLoading
            ? [1, 2, 3].map((i) => (
                <div key={i} className="p-6 rounded-lg border-2 border-gray-200 animate-pulse">
                  <div className="h-32 bg-gray-200 rounded" />
                </div>
              ))
            : (plans?.plans || []).map((plan: ShopifyPlanInfo) => {
                const isCurrent = plan.tier === currentTier;
                const config = PLAN_CONFIG[plan.tier];
                const isPending =
                  (subscribeMutation.isPending || changePlanMutation.isPending) &&
                  !isCurrent;

                return (
                  <div
                    key={plan.tier}
                    className={`relative p-6 rounded-lg border-2 transition-colors ${
                      isCurrent
                        ? 'border-green-500 bg-green-50/50'
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
                      <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-green-600 text-white text-xs font-medium rounded-full whitespace-nowrap">
                        Current Plan
                      </span>
                    )}

                    <div className="text-center mb-4">
                      <div className="flex justify-center mb-2">
                        {config?.icon}
                      </div>
                      <h3 className="text-lg font-semibold text-gray-900">{plan.name}</h3>
                      <div className="mt-1">
                        <span className="text-2xl font-bold text-gray-900">
                          ${plan.price_monthly}
                        </span>
                        <span className="text-sm text-gray-500">/month</span>
                      </div>
                      <p className="text-xs text-blue-600 mt-1">
                        {plan.trial_days}-day free trial
                      </p>
                    </div>

                    {/* Features */}
                    <ul className="space-y-2 mb-6">
                      {plan.features.map((feature) => (
                        <li key={feature} className="flex items-start gap-2 text-sm">
                          <Check className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
                          <span className="text-gray-600">{feature}</span>
                        </li>
                      ))}
                    </ul>

                    <Button
                      onClick={() =>
                        handleSubscribe(plan.tier as ShopifyBillingTier)
                      }
                      disabled={isCurrent || isPending}
                      variant={config?.popular ? 'primary' : 'secondary'}
                      size="sm"
                      className={`w-full ${config?.popular ? 'bg-purple-600 hover:bg-purple-700' : ''}`}
                      isLoading={isPending}
                    >
                      {isCurrent
                        ? 'Current Plan'
                        : hasActiveSub
                        ? 'Switch Plan'
                        : 'Start Free Trial'}
                    </Button>
                  </div>
                );
              })}
        </div>
      </Card>

      {/* Cancel Subscription */}
      {hasActiveSub && (
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Cancel Subscription</CardTitle>
              <p className="text-sm text-gray-500 mt-1">
                Cancel your subscription and downgrade to the free plan.
              </p>
            </div>
            <Button
              onClick={handleCancel}
              variant="secondary"
              size="sm"
              isLoading={cancelMutation.isPending}
              className="text-red-600 border-red-200 hover:bg-red-50"
            >
              Cancel Subscription
            </Button>
          </div>
        </Card>
      )}

      {/* Billing managed by Shopify notice */}
      <Card>
        <div className="flex items-center gap-3 text-sm text-gray-500">
          <Receipt className="w-5 h-5 text-gray-400" />
          <p>
            Billing is managed through your Shopify account.
            View invoices and receipts in your{' '}
            <a
              href="https://admin.shopify.com/settings/billing"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline"
            >
              Shopify billing settings <ExternalLink className="w-3 h-3 inline" />
            </a>
          </p>
        </div>
      </Card>
    </div>
  );
}

// =============================================================================
// MNEE BILLING UI (existing, extracted as component)
// =============================================================================

function MneeBillingPage() {
  const queryClient = useQueryClient();
  const { data: subscription, isLoading: subLoading, isRefetching } = useSubscription();
  const { data: plansData, isLoading: plansLoading } = usePlans();

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: paymentKeys.subscription() });
  };

  const isLoading = subLoading || plansLoading;
  const currentTier: SubscriptionTier = subscription?.tier || 'free';
  const isActive = subscription?.status === 'active';
  const plans = (plansData as PlansResponse)?.plans || [];

  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return null;
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const formatPrice = (price: string | undefined | null) => {
    if (!price) return '$0';
    const numPrice = parseFloat(price);
    if (isNaN(numPrice) || numPrice === 0) return '$0';
    return `$${numPrice.toFixed(2).replace(/\.00$/, '')}`;
  };

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
                You are currently on the{' '}
                <span className="font-medium capitalize">{currentTier}</span> plan
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
          </div>
        </div>

        {!isLoading && (
          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-white rounded-lg border border-gray-200">
                  {PLAN_CONFIG[currentTier]?.icon || <Zap className="w-5 h-5 text-blue-600" />}
                </div>
                <div>
                  <p className="font-medium text-gray-900 capitalize">
                    {subscription?.name || currentTier} Plan
                  </p>
                  <p className="text-sm text-gray-500">
                    {PLAN_CONFIG[currentTier]?.description}
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
            <p className="text-sm text-gray-500 mt-1">Upgrade to unlock more features</p>
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
                  <div className="flex justify-center mb-2">{config?.icon}</div>
                  <h3 className="text-lg font-semibold text-gray-900">{plan.name}</h3>
                  <div className="mt-1">
                    <span className="text-2xl font-bold text-gray-900">
                      {formatPrice(plan.monthly_price)}
                    </span>
                    <span className="text-sm text-gray-500">
                      {planTier === 'free' ? '/forever' : '/month'}
                    </span>
                  </div>
                </div>

                <ul className="space-y-2 mb-4">
                  {plan.features.slice(0, 4).map((feature) => (
                    <li key={feature} className="flex items-start gap-2 text-sm">
                      <Check className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
                      <span className="text-gray-600">{feature}</span>
                    </li>
                  ))}
                </ul>

                {isCurrent ? (
                  <Button variant="secondary" size="sm" className="w-full" disabled>
                    Current Plan
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

      {/* Payment Method */}
      <Card>
        <CardTitle>Payment Method</CardTitle>
        <p className="text-sm text-gray-500 mt-1">Manage your payment information</p>
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
    </div>
  );
}

// =============================================================================
// MAIN PAGE — Auto-detects Shopify vs Standalone
// =============================================================================

export default function BillingSettingsPage() {
  return (
    <Suspense fallback={<div className="space-y-6"><Card><div className="animate-pulse"><div className="h-6 bg-gray-200 rounded w-1/3 mb-4" /><div className="h-16 bg-gray-200 rounded" /></div></Card></div>}>
      <BillingSettingsContent />
    </Suspense>
  );
}

function BillingSettingsContent() {
  const { isEmbedded, shopDomain, isSessionReady } = useShopifyEmbedded();

  // Wait for embedded context to resolve
  if (!isSessionReady) {
    return (
      <div className="space-y-6">
        <Card>
          <div className="animate-pulse">
            <div className="h-6 bg-gray-200 rounded w-1/3 mb-4" />
            <div className="h-16 bg-gray-200 rounded" />
          </div>
        </Card>
      </div>
    );
  }

  if (isEmbedded) {
    return <ShopifyBillingPage shop={shopDomain} />;
  }

  return <MneeBillingPage />;
}


