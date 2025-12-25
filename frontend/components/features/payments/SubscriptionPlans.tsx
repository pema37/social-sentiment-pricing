// frontend/components/features/payments/SubscriptionPlans.tsx

'use client';

import { useState } from 'react';
import { Check, Star, Zap, Building2, Sparkles } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { usePlans, useSubscription, useSubscribe } from '@/lib/hooks/use-payments';
import { useToast } from '@/lib/hooks/use-toast';
import type { SubscriptionPlan, SubscriptionTier } from '@/types/payment';

const TIER_ICONS: Record<SubscriptionTier, React.ReactNode> = {
  free: <Sparkles className="h-6 w-6" />,
  starter: <Zap className="h-6 w-6" />,
  professional: <Star className="h-6 w-6" />,
  enterprise: <Building2 className="h-6 w-6" />,
};

const TIER_COLORS: Record<SubscriptionTier, string> = {
  free: 'bg-gray-100 text-gray-600',
  starter: 'bg-blue-100 text-blue-600',
  professional: 'bg-purple-100 text-purple-600',
  enterprise: 'bg-orange-100 text-orange-600',
};

interface PlanCardProps {
  plan: SubscriptionPlan;
  currentTier: SubscriptionTier;
  onSelect: (tier: SubscriptionTier) => void;
  isLoading: boolean;
}

function PlanCard({ plan, currentTier, onSelect, isLoading }: PlanCardProps) {
  const isCurrentPlan = plan.id === currentTier;
  const isProfessional = plan.id === 'professional';

  return (
    <Card
      className={`p-6 relative ${
        isProfessional ? 'border-2 border-purple-500 shadow-lg' : ''
      } ${isCurrentPlan ? 'bg-green-50 border-green-500' : ''}`}
    >
      {isProfessional && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="bg-purple-500 text-white text-xs font-bold px-3 py-1 rounded-full">
            MOST POPULAR
          </span>
        </div>
      )}

      {isCurrentPlan && (
        <div className="absolute -top-3 right-4">
          <span className="bg-green-500 text-white text-xs font-bold px-3 py-1 rounded-full">
            CURRENT PLAN
          </span>
        </div>
      )}

      <div className="text-center mb-6">
        <div
          className={`inline-flex p-3 rounded-full ${TIER_COLORS[plan.id]} mb-3`}
        >
          {TIER_ICONS[plan.id]}
        </div>
        <h3 className="text-xl font-bold">{plan.name}</h3>
        <div className="mt-2">
          <span className="text-3xl font-bold">${plan.monthly_price}</span>
          <span className="text-gray-500">/month</span>
        </div>
        {plan.id !== 'free' && (
          <p className="text-sm text-gray-500 mt-1">
            Paid in MNEE (1 MNEE = $1 USD)
          </p>
        )}
      </div>

      <div className="space-y-3 mb-6">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">Products</span>
          <span className="font-medium">
            {plan.products_limit === -1 ? 'Unlimited' : plan.products_limit}
          </span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">Competitors</span>
          <span className="font-medium">
            {plan.competitors_limit === -1 ? 'Unlimited' : plan.competitors_limit}
          </span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">API Calls</span>
          <span className="font-medium">
            {plan.api_calls_limit === -1
              ? 'Unlimited'
              : plan.api_calls_limit.toLocaleString()}
          </span>
        </div>
      </div>

      <div className="border-t pt-4 mb-6">
        <p className="text-sm font-medium mb-2">Features:</p>
        <ul className="space-y-2">
          {plan.features.map((feature, index) => (
            <li key={index} className="flex items-start gap-2 text-sm">
              <Check className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
              <span>{feature}</span>
            </li>
          ))}
        </ul>
      </div>

      <Button
        onClick={() => onSelect(plan.id)}
        disabled={isCurrentPlan || isLoading}
        variant={isProfessional ? 'primary' : 'secondary'}
        className={`w-full ${isProfessional ? 'bg-purple-600 hover:bg-purple-700' : ''}`}
        isLoading={isLoading}
      >
        {isCurrentPlan
          ? 'Current Plan'
          : plan.id === 'free'
          ? 'Downgrade to Free'
          : `Upgrade to ${plan.name}`}
      </Button>
    </Card>
  );
}

export function SubscriptionPlans() {
  const { data: plansData, isLoading: plansLoading } = usePlans();
  const { data: subscription, isLoading: subLoading } = useSubscription();
  const subscribeMutation = useSubscribe();
  const toast = useToast();

  const [selectedTier, setSelectedTier] = useState<SubscriptionTier | null>(null);
  const [paymentInfo, setPaymentInfo] = useState<{
    status: string;
    amount: string;
    payment_address: string;
    memo: string;
    instructions: {
      step1: string;
      step2: string;
      step3: string;
      step4: string;
    };
  } | null>(null);

  const handleSelectPlan = async (tier: SubscriptionTier) => {
    setSelectedTier(tier);

    try {
      const result = await subscribeMutation.mutateAsync(tier);
      setPaymentInfo(result);

      if (tier === 'free') {
        toast.success({
          title: 'Plan Changed',
          message: 'You are now on the Free plan.',
        });
      } else {
        toast.info({
          title: 'Payment Required',
          message: `Send ${result.amount} MNEE to complete your subscription.`,
        });
      }
    } catch (error) {
      toast.error({
        title: 'Error',
        message: 'Failed to process subscription. Please try again.',
      });
    }
  };

  if (plansLoading || subLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="p-6 animate-pulse">
            <div className="h-32 bg-gray-200 rounded mb-4"></div>
            <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
            <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          </Card>
        ))}
      </div>
    );
  }

  const plans = plansData?.plans || [];
  const currentTier = subscription?.tier || 'free';

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {plans.map((plan) => (
          <PlanCard
            key={plan.id}
            plan={plan}
            currentTier={currentTier}
            onSelect={handleSelectPlan}
            isLoading={subscribeMutation.isPending && selectedTier === plan.id}
          />
        ))}
      </div>

      {paymentInfo && paymentInfo.status === 'pending' && (
        <Card className="p-6 bg-blue-50 border-blue-200">
          <h3 className="text-lg font-semibold mb-4">Complete Your Payment</h3>
          <div className="space-y-3">
            <div>
              <span className="text-sm text-gray-600">Amount:</span>
              <p className="font-bold text-xl">{paymentInfo.amount} MNEE</p>
            </div>
            <div>
              <span className="text-sm text-gray-600">Send to:</span>
              <p className="font-mono text-sm bg-white p-2 rounded border break-all">
                {paymentInfo.payment_address}
              </p>
            </div>
            <div>
              <span className="text-sm text-gray-600">Memo (required):</span>
              <p className="font-mono text-sm bg-white p-2 rounded border">
                {paymentInfo.memo}
              </p>
            </div>
            <div className="border-t pt-3">
              <p className="text-sm text-gray-600">
                <strong>Instructions:</strong>
              </p>
              <ol className="list-decimal list-inside text-sm space-y-1 mt-2">
                <li>{paymentInfo.instructions.step1}</li>
                <li>{paymentInfo.instructions.step2}</li>
                <li>{paymentInfo.instructions.step3}</li>
                <li>{paymentInfo.instructions.step4}</li>
              </ol>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
