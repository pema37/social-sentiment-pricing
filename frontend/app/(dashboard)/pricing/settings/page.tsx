// Pricing Settings Page
// Configure auto-approve thresholds and notifications

'use client';

/* eslint-disable react-hooks/set-state-in-effect */

import { useRouter } from 'next/navigation';
import { useState, useCallback, useEffect, useMemo } from 'react';
import { ArrowLeft, Settings, Save, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { cn } from '@/lib/utils';
import {
  usePricingSettings,
  useUpdatePricingSettings,
} from '@/lib/hooks/use-pricing';

// ============================================
// TYPES
// ============================================

interface FormData {
  auto_approve_enabled: boolean;
  auto_approve_max_increase: string;
  auto_approve_max_decrease: string;
  auto_approve_min_confidence: string;
  global_cooldown_hours: string;
}

// ============================================
// COMPONENT
// ============================================

export default function PricingSettingsPage() {
  const router = useRouter();

  // Fetch current settings
  const { data: settings, isLoading, isError, refetch } = usePricingSettings();
  const updateMutation = useUpdatePricingSettings();

  // Compute initial form data from settings - use correct backend field names
  const initialFormData = useMemo<FormData>(() => ({
    auto_approve_enabled: settings?.auto_approve_enabled ?? false,
    auto_approve_max_increase: (settings?.auto_approve_max_increase ?? 5).toString(),
    auto_approve_max_decrease: (settings?.auto_approve_max_decrease ?? 10).toString(),
    auto_approve_min_confidence: (settings?.auto_approve_min_confidence ?? 0.7).toString(),
    global_cooldown_hours: (settings?.global_cooldown_hours ?? 24).toString(),
  }), [settings]);

  // Form state - re-initialize when settings change
  const [formData, setFormData] = useState<FormData>(initialFormData);
  const [hasChanges, setHasChanges] = useState(false);

  // Reset form when settings change
  useEffect(() => {
    setFormData(initialFormData);
    setHasChanges(false);
  }, [initialFormData]);

  // Handle field changes
  const handleChange = useCallback(
    (field: keyof FormData, value: string | boolean) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      setHasChanges(true);
    },
    []
  );

  // Handle save - send correct backend field names
  const handleSave = useCallback(async () => {
    try {
      await updateMutation.mutateAsync({
        auto_approve_enabled: formData.auto_approve_enabled,
        auto_approve_max_increase: parseFloat(formData.auto_approve_max_increase),
        auto_approve_max_decrease: parseFloat(formData.auto_approve_max_decrease),
        auto_approve_min_confidence: parseFloat(formData.auto_approve_min_confidence),
        global_cooldown_hours: parseInt(formData.global_cooldown_hours),
      });
      toast.success('Settings saved successfully');
      setHasChanges(false);
    } catch (error) {
      toast.error('Failed to save settings');
      console.error('Save error:', error);
    }
  }, [formData, updateMutation]);

  // Loading state
  if (isLoading) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="mb-6">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push('/pricing')}
            className="mb-4"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Pricing
          </Button>
          <div className="h-8 w-48 bg-gray-200 rounded animate-pulse mb-2" />
          <div className="h-5 w-72 bg-gray-100 rounded animate-pulse" />
        </div>

        <div className="space-y-6">
          {[...Array(3)].map((_, i) => (
            <Card key={i} padding="md">
              <div className="animate-pulse space-y-4">
                <div className="h-6 w-40 bg-gray-200 rounded" />
                <div className="h-10 w-full bg-gray-100 rounded-lg" />
              </div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push('/pricing')}
          className="mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Pricing
        </Button>

        <Card padding="md" className="bg-red-50 border-red-200">
          <h3 className="text-red-800 font-medium mb-2">Error Loading Settings</h3>
          <p className="text-red-600 text-sm mb-4">
            Could not load pricing settings. Please try again.
          </p>
          <Button variant="secondary" size="sm" onClick={() => refetch()}>
            Try Again
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push('/pricing')}
            className="mb-4"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Pricing
          </Button>

          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Settings className="h-6 w-6 text-gray-600" />
            Pricing Settings
          </h1>
          <p className="text-gray-600 mt-1">
            Configure automatic pricing behavior
          </p>
        </div>

        <Button
          variant="primary"
          onClick={handleSave}
          disabled={!hasChanges || updateMutation.isPending}
        >
          {updateMutation.isPending ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          Save Changes
        </Button>
      </div>

      <div className="space-y-6">
        {/* Auto-Approve Settings */}
        <Card padding="md">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Automatic Price Approval
          </h2>

          <div className="space-y-6">
            {/* Auto-approve toggle */}
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">Enable Auto-Approve</p>
                <p className="text-sm text-gray-500">
                  Automatically approve low-risk price recommendations
                </p>
              </div>
              <button
                type="button"
                onClick={() => handleChange('auto_approve_enabled', !formData.auto_approve_enabled)}
                className={cn(
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                  formData.auto_approve_enabled ? 'bg-blue-600' : 'bg-gray-200'
                )}
              >
                <span
                  className={cn(
                    'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                    formData.auto_approve_enabled ? 'translate-x-6' : 'translate-x-1'
                  )}
                />
              </button>
            </div>

            {/* Max auto-approve increase */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Auto-Approve Increase (%)
              </label>
              <p className="text-sm text-gray-500 mb-2">
                Auto-approve price increases up to this percentage
              </p>
              <input
                type="number"
                value={formData.auto_approve_max_increase}
                onChange={(e) => handleChange('auto_approve_max_increase', e.target.value)}
                min="0"
                max="100"
                step="0.5"
                disabled={!formData.auto_approve_enabled}
                className={cn(
                  'w-full max-w-xs px-3 py-2 border border-gray-300 rounded-lg text-sm',
                  'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                  'disabled:bg-gray-100 disabled:text-gray-500'
                )}
              />
            </div>

            {/* Max auto-approve decrease */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Auto-Approve Decrease (%)
              </label>
              <p className="text-sm text-gray-500 mb-2">
                Auto-approve price decreases up to this percentage
              </p>
              <input
                type="number"
                value={formData.auto_approve_max_decrease}
                onChange={(e) => handleChange('auto_approve_max_decrease', e.target.value)}
                min="0"
                max="100"
                step="0.5"
                disabled={!formData.auto_approve_enabled}
                className={cn(
                  'w-full max-w-xs px-3 py-2 border border-gray-300 rounded-lg text-sm',
                  'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                  'disabled:bg-gray-100 disabled:text-gray-500'
                )}
              />
            </div>
          </div>
        </Card>

        {/* Confidence Settings */}
        <Card padding="md">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Confidence Threshold
          </h2>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Minimum Confidence Score
            </label>
            <p className="text-sm text-gray-500 mb-2">
              Only auto-approve recommendations above this confidence level (0.0 - 1.0)
            </p>
            <input
              type="number"
              value={formData.auto_approve_min_confidence}
              onChange={(e) => handleChange('auto_approve_min_confidence', e.target.value)}
              min="0"
              max="1"
              step="0.05"
              className="w-full max-w-xs px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </Card>

        {/* Cooldown Settings */}
        <Card padding="md">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Cooldown Period
          </h2>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Global Cooldown (hours)
            </label>
            <p className="text-sm text-gray-500 mb-2">
              Minimum time between price changes for the same product
            </p>
            <input
              type="number"
              value={formData.global_cooldown_hours}
              onChange={(e) => handleChange('global_cooldown_hours', e.target.value)}
              min="1"
              max="720"
              step="1"
              className="w-full max-w-xs px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </Card>
      </div>
    </div>
  );
}
