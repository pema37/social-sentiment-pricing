// frontend/app/(dashboard)/payments/page.tsx

'use client';

import { SectionHeader } from '@/components/ui/SectionHeader';
import {
  BsvWalletCard,
  CurrentPlan,
  SubscriptionPlans,
  PaymentHistory,
} from '@/components/features/payments';

export default function PaymentsPage() {
  return (
    <div className="space-y-8">
      <SectionHeader
        title="Payments & Subscription"
        description="Manage your BSV wallet and subscription plan. Pay with MNEE stablecoin."
      />

      {/* Wallet and Current Plan - Side by Side on Desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <BsvWalletCard />
        <CurrentPlan />
      </div>

      {/* Subscription Plans */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Subscription Plans</h2>
        <SubscriptionPlans />
      </div>

      {/* Payment History */}
      <PaymentHistory />

      {/* Info Section */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="font-semibold text-blue-900 mb-2">About MNEE Payments</h3>
        <div className="text-sm text-blue-800 space-y-2">
          <p>
            <strong>MNEE</strong> is a BSV-based stablecoin where 1 MNEE = $1 USD.
          </p>
          <p>
            To make payments, you need a BSV wallet like{' '}
            <a
              href="https://handcash.io"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:no-underline"
            >
              HandCash
            </a>{' '}
            or{' '}
            <a
              href="https://relayx.com"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:no-underline"
            >
              RelayX
            </a>
            .
          </p>
          <p>
            Transactions are fast and have minimal fees compared to traditional
            payment processors.
          </p>
        </div>
      </div>
    </div>
  );
}
