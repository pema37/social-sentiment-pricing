// Billing Settings Page
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
} from 'lucide-react';

const plans = [
  {
    id: 'free',
    name: 'Free',
    price: '$0',
    period: 'forever',
    description: 'Get started with basic features',
    features: [
      'Up to 10 products',
      'Basic sentiment analysis',
      'Email alerts',
      'Community support',
    ],
    current: true,
  },
  {
    id: 'pro',
    name: 'Pro',
    price: '$49',
    period: '/month',
    description: 'For growing businesses',
    features: [
      'Up to 100 products',
      'Advanced sentiment analysis',
      'Competitor tracking',
      'Auto-pricing rules',
      'Priority support',
    ],
    current: false,
    popular: true,
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: 'Custom',
    period: '',
    description: 'For large organizations',
    features: [
      'Unlimited products',
      'Custom integrations',
      'Dedicated account manager',
      'SLA guarantee',
      'Custom AI training',
    ],
    current: false,
  },
];

export default function BillingSettingsPage() {
  return (
    <div className="space-y-6">
      {/* Current Plan */}
      <Card>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>Current Plan</CardTitle>
            <p className="text-sm text-gray-500 mt-1">
              You are currently on the Free plan
            </p>
          </div>
          <span className="px-3 py-1 bg-green-100 text-green-700 text-sm font-medium rounded-full">
            Active
          </span>
        </div>

        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-white rounded-lg border border-gray-200">
                <Zap className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="font-medium text-gray-900">Free Plan</p>
                <p className="text-sm text-gray-500">Basic features for getting started</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-2xl font-semibold text-gray-900">$0</p>
              <p className="text-sm text-gray-500">forever</p>
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center gap-4 text-sm text-gray-500">
          <div className="flex items-center gap-1">
            <Calendar className="w-4 h-4" />
            <span>No renewal date</span>
          </div>
        </div>
      </Card>

      {/* Available Plans */}
      <Card>
        <CardTitle>Available Plans</CardTitle>
        <p className="text-sm text-gray-500 mt-1">
          Upgrade to unlock more features
        </p>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className={`relative p-4 rounded-lg border-2 transition-colors ${
                plan.current
                  ? 'border-blue-500 bg-blue-50/50'
                  : plan.popular
                  ? 'border-purple-200 hover:border-purple-300'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              {plan.popular && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-purple-600 text-white text-xs font-medium rounded-full">
                  Popular
                </span>
              )}
              
              <div className="text-center mb-4">
                <h3 className="text-lg font-semibold text-gray-900">{plan.name}</h3>
                <div className="mt-1">
                  <span className="text-2xl font-bold text-gray-900">{plan.price}</span>
                  <span className="text-sm text-gray-500">{plan.period}</span>
                </div>
                <p className="text-xs text-gray-500 mt-1">{plan.description}</p>
              </div>

              <ul className="space-y-2 mb-4">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2 text-sm">
                    <Check className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
                    <span className="text-gray-600">{feature}</span>
                  </li>
                ))}
              </ul>

              {plan.current ? (
                <Button variant="secondary" size="sm" className="w-full" disabled>
                  Current Plan
                </Button>
              ) : plan.id === 'enterprise' ? (
                <Button variant="secondary" size="sm" className="w-full">
                  <Building2 className="w-4 h-4 mr-1" />
                  Contact Sales
                </Button>
              ) : (
                <Button variant="primary" size="sm" className="w-full">
                  Upgrade
                </Button>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Payment Method */}
      <Card>
        <CardTitle>Payment Method</CardTitle>
        <p className="text-sm text-gray-500 mt-1">
          Manage your payment information
        </p>

        <div className="mt-6 p-4 border border-dashed border-gray-300 rounded-lg text-center">
          <CreditCard className="w-8 h-8 text-gray-400 mx-auto mb-2" />
          <p className="text-sm text-gray-600">No payment method on file</p>
          <p className="text-xs text-gray-500 mt-1">
            Add a payment method when you upgrade to a paid plan
          </p>
          <Button variant="secondary" size="sm" className="mt-4" disabled>
            Add Payment Method
          </Button>
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
          <Button variant="ghost" size="sm" disabled>
            <ExternalLink className="w-4 h-4 mr-1" />
            View All
          </Button>
        </div>

        <div className="mt-6 flex flex-col items-center justify-center py-8 text-gray-500">
          <Receipt className="w-8 h-8 mb-2 text-gray-400" />
          <p className="text-sm">No billing history</p>
          <p className="text-xs text-gray-400 mt-1">
            Invoices will appear here when you upgrade
          </p>
        </div>
      </Card>
    </div>
  );
}
