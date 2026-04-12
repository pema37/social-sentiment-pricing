export const dynamic = 'force-dynamic';
// Create New Pricing Rule Page
// Form for creating a new pricing rule

'use client';

import { Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { RuleForm } from '@/components/features/pricing/RuleForm';
import { usePricingRule } from '@/lib/hooks/use-pricing';

// ============================================
// PAGE COMPONENT
// ============================================

export default function NewPricingRulePage() {
  return (
    <Suspense fallback={<div className="p-6 max-w-3xl mx-auto animate-pulse"><div className="h-10 bg-gray-200 rounded-lg mb-4" /><div className="h-32 bg-gray-200 rounded-lg" /></div>}>
      <NewPricingRuleContent />
    </Suspense>
  );
}

function NewPricingRuleContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const duplicateId = searchParams.get('duplicate');

  // If duplicating, fetch the source rule
  const { data: sourceRule, isLoading: isLoadingSource } = usePricingRule(duplicateId);

  const handleSuccess = () => {
    router.push('/pricing/rules');
  };

  const handleCancel = () => {
    router.push('/pricing/rules');
  };

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push('/pricing/rules')}
          className="mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Rules
        </Button>

        <h1 className="text-2xl font-bold text-gray-900">
          {duplicateId ? 'Duplicate Rule' : 'Create New Rule'}
        </h1>
        <p className="text-gray-600 mt-1">
          {duplicateId
            ? 'Create a copy of an existing rule with modifications'
            : 'Define conditions and actions for automatic pricing'}
        </p>
      </div>

      {/* Form */}
      {duplicateId && isLoadingSource ? (
        <div className="animate-pulse space-y-4">
          <div className="h-10 bg-gray-200 rounded-lg" />
          <div className="h-32 bg-gray-200 rounded-lg" />
          <div className="h-10 bg-gray-200 rounded-lg" />
        </div>
      ) : (
        <RuleForm
          initialData={
            sourceRule
              ? {
                  ...sourceRule,
                  name: `${sourceRule.name} (Copy)`,
                }
              : undefined
          }
          onSuccess={handleSuccess}
          onCancel={handleCancel}
        />
      )}
    </div>
  );
}
