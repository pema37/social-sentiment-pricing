// Edit Pricing Rule Page
// Form for editing an existing pricing rule

'use client';

import { useRouter, useParams } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { RuleForm } from '@/components/features/pricing/RuleForm';
import { usePricingRule } from '@/lib/hooks/use-pricing';

// ============================================
// PAGE COMPONENT
// ============================================

export default function EditPricingRulePage() {
  const router = useRouter();
  const params = useParams();
  const ruleId = params.id as string;

  // Fetch the rule
  const { data: rule, isLoading, isError } = usePricingRule(ruleId);

  const handleSuccess = () => {
    router.push('/pricing/rules');
  };

  const handleCancel = () => {
    router.push('/pricing/rules');
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
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

          <div className="h-8 w-48 bg-gray-200 rounded animate-pulse mb-2" />
          <div className="h-5 w-64 bg-gray-100 rounded animate-pulse" />
        </div>

        <div className="space-y-6">
          {[...Array(4)].map((_, i) => (
            <Card key={i} padding="md">
              <div className="animate-pulse space-y-4">
                <div className="h-6 w-40 bg-gray-200 rounded" />
                <div className="h-10 w-full bg-gray-100 rounded-lg" />
                <div className="h-10 w-full bg-gray-100 rounded-lg" />
              </div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (isError || !rule) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push('/pricing/rules')}
          className="mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Rules
        </Button>

        <Card padding="md" className="bg-red-50 border-red-200">
          <h3 className="text-red-800 font-medium mb-2">Error Loading Rule</h3>
          <p className="text-red-600 text-sm mb-4">
            The rule could not be found or there was an error loading it.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => router.push('/pricing/rules')}
          >
            Return to Rules
          </Button>
        </Card>
      </div>
    );
  }

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

        <h1 className="text-2xl font-bold text-gray-900">Edit Rule</h1>
        <p className="text-gray-600 mt-1">
          Modify the conditions and actions for {rule.name}
        </p>
      </div>

      {/* Form */}
      <RuleForm
        initialData={rule}
        ruleId={ruleId}
        onSuccess={handleSuccess}
        onCancel={handleCancel}
      />
    </div>
  );
}
