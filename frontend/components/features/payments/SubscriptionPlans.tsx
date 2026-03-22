'use client';

import { useState, useEffect, useRef } from 'react';
import { Check, Star, Zap, Building2, Sparkles } from 'lucide-react';
import { useAccount } from 'wagmi';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { PayWithMNEE } from './PayWithMNEE';
import { usePlans, useSubscription, useSubscribe, useConfirmPayment, useDowngradeToFree } from '@/lib/hooks/use-payments';
import { useToast } from '@/lib/hooks/use-toast';
import type { SubscriptionPlan, SubscriptionTier } from '@/types/payment';
import type { PaymentNetwork } from '@/app/(dashboard)/payments/page';

// =============================================================================
// Constants
// =============================================================================

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

// =============================================================================
// Types
// =============================================================================

interface SubscriptionPlansProps {
  activeNetwork: PaymentNetwork;
}

interface PlanCardProps {
  plan: SubscriptionPlan;
  currentTier: SubscriptionTier;
  onSelect: (tier: SubscriptionTier) => void;
  isLoading: boolean;
}

interface PaymentInfo {
  status: string;
  amount: string;
  payment_address: string;
  payment_id: string;  // Added for confirm call
  network: string;
  memo: string;
  tier: SubscriptionTier;
}

// =============================================================================
// Plan Card Component
// =============================================================================

function PlanCard({ plan, currentTier, onSelect, isLoading }: PlanCardProps) {
  const isCurrentPlan = plan.id === currentTier;
  const isProfessional = plan.id === 'professional';
  
  // Determine if this is a lower paid tier (not free, but below current)
  const tierOrder: SubscriptionTier[] = ['free', 'starter', 'professional', 'enterprise'];
  const currentIndex = tierOrder.indexOf(currentTier);
  const planIndex = tierOrder.indexOf(plan.id);
  const isLowerPaidTier = plan.id !== 'free' && planIndex < currentIndex;

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
        disabled={isCurrentPlan || isLoading || isLowerPaidTier}
        variant={isProfessional ? 'primary' : 'secondary'}
        className={`w-full ${isProfessional ? 'bg-purple-600 hover:bg-purple-700' : ''}`}
        isLoading={isLoading}
      >
        {isCurrentPlan
          ? 'Current Plan'
          : isLowerPaidTier
          ? 'Lower Tier'
          : plan.id === 'free'
          ? 'Downgrade to Free'
          : `Upgrade to ${plan.name}`}
      </Button>
    </Card>
  );
}

// =============================================================================
// Ethereum Payment Component
// =============================================================================

interface EthereumPaymentProps {
  paymentInfo: PaymentInfo;
  onSuccess: (txHash: string) => void;
  onCancel: () => void;
}

function EthereumPayment({ paymentInfo, onSuccess, onCancel }: EthereumPaymentProps) {
  const { isConnected } = useAccount();
  
  if (!paymentInfo.payment_address) {
    return (
      <Card className="p-6 bg-red-50 border-red-200">
        <h3 className="text-lg font-semibold text-red-800 mb-2">Configuration Error</h3>
        <p className="text-sm text-red-700">
          Ethereum payments are not configured. Please use BSV network or contact support.
        </p>
        <Button onClick={onCancel} variant="secondary" className="mt-4">
          Go Back
        </Button>
      </Card>
    );
  }

  if (!isConnected) {
    return (
      <Card className="p-6 bg-yellow-50 border-yellow-200">
        <h3 className="text-lg font-semibold text-yellow-800 mb-2">Wallet Not Connected</h3>
        <p className="text-sm text-yellow-700 mb-4">
          Please connect your MetaMask or WalletConnect wallet to pay with MNEE on Ethereum.
        </p>
        <Button onClick={onCancel} variant="secondary">
          Go Back
        </Button>
      </Card>
    );
  }

  return (
    <Card className="p-6 bg-purple-50 border-purple-200">
      <h3 className="text-lg font-semibold text-purple-900 mb-4">
        Complete Your Payment
      </h3>
      
      <div className="space-y-4 mb-6">
        <div>
          <span className="text-sm text-gray-600">Plan:</span>
          <p className="font-semibold capitalize">{paymentInfo.tier}</p>
        </div>
        <div>
          <span className="text-sm text-gray-600">Amount:</span>
          <p className="font-bold text-2xl text-purple-700">{paymentInfo.amount} MNEE</p>
          <p className="text-sm text-gray-500">≈ ${paymentInfo.amount} USD</p>
        </div>
        <div>
          <span className="text-sm text-gray-600">Sending to:</span>
          <p className="font-mono text-xs bg-white p-2 rounded border break-all">
            {paymentInfo.payment_address}
          </p>
        </div>
      </div>

      {/* PayWithMNEE triggers MetaMask! */}
      <PayWithMNEE
        amount={paymentInfo.amount}
        recipients={paymentInfo.payment_address}
        orderId={paymentInfo.memo}
        onSuccess={onSuccess}
        onError={(error) => {
          console.error('Payment failed:', error);
        }}
        buttonText={`Pay ${paymentInfo.amount} MNEE`}
      />

      <Button 
        onClick={onCancel} 
        variant="secondary" 
        className="w-full mt-3"
      >
        Cancel
      </Button>
    </Card>
  );
}

// =============================================================================
// BSV Payment Component (Manual)
// =============================================================================

interface BsvPaymentProps {
  paymentInfo: PaymentInfo;
  onCancel: () => void;
}

function BsvPayment({ paymentInfo, onCancel }: BsvPaymentProps) {
  return (
    <Card className="p-6 bg-orange-50 border-orange-200">
      <h3 className="text-lg font-semibold text-orange-900 mb-4">
        Complete Your Payment
      </h3>
      
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
          <p className="text-sm font-medium text-gray-700">Instructions:</p>
          <ol className="list-decimal list-inside text-sm space-y-1 mt-2 text-gray-600">
            <li>Open your BSV wallet (HandCash or RelayX)</li>
            <li>Send exactly {paymentInfo.amount} MNEE to the address above</li>
            <li>Include memo: {paymentInfo.memo}</li>
            <li>Wait for confirmation (usually &lt; 1 minute)</li>
          </ol>
        </div>
      </div>

      <Button 
        onClick={onCancel} 
        variant="secondary" 
        className="w-full mt-4"
      >
        Cancel
      </Button>
    </Card>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function SubscriptionPlans({ activeNetwork }: SubscriptionPlansProps) {
  const { data: plansData, isLoading: plansLoading } = usePlans();
  const { data: subscription, isLoading: subLoading, refetch: refetchSubscription } = useSubscription();
  const subscribeMutation = useSubscribe();
  const confirmMutation = useConfirmPayment();
  const downgradeToFreeMutation = useDowngradeToFree();
  const toast = useToast();

  const [selectedTier, setSelectedTier] = useState<SubscriptionTier | null>(null);
  const [paymentInfo, setPaymentInfo] = useState<PaymentInfo | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const refetchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (refetchTimerRef.current) {
        clearTimeout(refetchTimerRef.current);
      }
    };
  }, []);

  // Reset payment when network changes
  useEffect(() => {
    setPaymentInfo(null);
    setSelectedTier(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeNetwork]);

  const handleSelectPlan = async (tier: SubscriptionTier) => {
    setSelectedTier(tier);

    try {
      // Handle downgrade to free separately (no payment needed)
      if (tier === 'free') {
        await downgradeToFreeMutation.mutateAsync();
        toast.success({
          title: 'Plan Changed',
          message: 'You are now on the Free plan.',
        });
        setSelectedTier(null);
        refetchSubscription();
        return;
      }

      // For paid tiers, create payment request
      const result = await subscribeMutation.mutateAsync({ 
        tier, 
        network: activeNetwork
      });
      
      setPaymentInfo({
        status: 'pending',
        amount: result.amount,
        payment_address: result.payment_address,
        payment_id: result.payment_id,
        network: activeNetwork,
        memo: result.memo,
        tier: tier,
      });

      toast.info({
        title: 'Payment Required',
        message: `Send ${result.amount} MNEE to complete your subscription.`,
      });
    } catch (error) {
      console.error('Subscribe error:', error);
      toast.error({
        title: 'Error',
        message: 'Failed to process subscription. Please try again.',
      });
      setSelectedTier(null);
    }
  };

  const handlePaymentSuccess = async (txHash: string) => {
    console.log('Payment txHash:', txHash);

    if (!paymentInfo?.payment_id) {
      toast.error({
        title: 'Error',
        message: 'Payment ID not found. Please try again.',
      });
      return;
    }

    setIsConfirming(true);

    try {
      const response = await confirmMutation.mutateAsync({
        paymentId: paymentInfo.payment_id,
        data: {
          transaction_hash: txHash,
          network: paymentInfo.network,
        },
      });

      if (response.success) {
        toast.success({
          title: 'Subscription Activated!',
          message: `You are now on the ${response.subscription_tier || paymentInfo.tier} plan.`,
        });
      } else {
        toast.success({
          title: 'Payment Received!',
          message: response.message || 'Your subscription is being activated.',
        });
      }
    } catch (error) {
      console.error('Confirm error:', error);
      toast.warning({
        title: 'Payment Sent',
        message: 'Transaction confirmed. Subscription will activate shortly.',
      });
    } finally {
      setIsConfirming(false);
      setPaymentInfo(null);
      setSelectedTier(null);
      // Refetch subscription to get updated tier
      refetchTimerRef.current = setTimeout(() => {
        refetchSubscription();
      }, 2000);
    }
  };

  const handleCancelPayment = () => {
    setPaymentInfo(null);
    setSelectedTier(null);
  };

  // Loading state
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
      {/* Plan Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {plans.map((plan) => (
          <PlanCard
            key={plan.id}
            plan={plan}
            currentTier={currentTier}
            onSelect={handleSelectPlan}
            isLoading={(subscribeMutation.isPending || downgradeToFreeMutation.isPending) && selectedTier === plan.id}
          />
        ))}
      </div>

      {/* Confirming State */}
      {isConfirming && (
        <Card className="p-6 bg-blue-50 border-blue-200">
          <div className="flex items-center justify-center gap-3">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
            <span className="text-blue-800 font-medium">Confirming payment...</span>
          </div>
        </Card>
      )}

      {/* Payment Section - Network Aware! */}
      {paymentInfo && paymentInfo.status === 'pending' && !isConfirming && (
        <>
          {activeNetwork === 'ethereum' ? (
            <EthereumPayment
              paymentInfo={paymentInfo}
              onSuccess={handlePaymentSuccess}
              onCancel={handleCancelPayment}
            />
          ) : (
            <BsvPayment
              paymentInfo={paymentInfo}
              onCancel={handleCancelPayment}
            />
          )}
        </>
      )}
    </div>
  );
}

export default SubscriptionPlans;


