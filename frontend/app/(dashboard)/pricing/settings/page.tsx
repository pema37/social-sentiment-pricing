// Pricing Settings Page
// Configure auto-apply, approval thresholds, and notifications

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
import type { AlertChannel } from '@/types';

// ============================================
// TYPES
// ============================================

interface FormData {
  auto_apply_enabled: boolean;
  auto_apply_max_percent: string;
  require_approval_above: string;
  min_confidence_threshold: string;
  default_cooldown_hours: string;
  notification_channels: AlertChannel[];
}

// ============================================
// CONFIG
// ============================================

const notificationChannelOptions: { value: AlertChannel; label: string; description: string }[] = [
  { value: 'email', label: 'Email', description: 'Receive email notifications' },
  { value: 'slack', label: 'Slack', description: 'Send to Slack channel' },
  { value: 'webhook', label: 'Webhook', description: 'POST to custom URL' },
  { value: 'in_app', label: 'In-App', description: 'Show in dashboard' },
];

// ============================================
// COMPONENT
// ============================================

export default function PricingSettingsPage() {
  const router = useRouter();

  // Fetch current settings
  const { data: settings, isLoading, isError, refetch } = usePricingSettings();
  const updateMutation = useUpdatePricingSettings();

  // Compute initial form data from settings
  const initialFormData = useMemo<FormData>(() => ({
    auto_apply_enabled: settings?.auto_apply_enabled ?? false,
    auto_apply_max_percent: settings?.auto_apply_max_percent ?? '5',
    require_approval_above: settings?.require_approval_above ?? '10',
    min_confidence_threshold: (settings?.min_confidence_threshold ?? 0.7).toString(),
    default_cooldown_hours: (settings?.default_cooldown_hours ?? 24).toString(),
    notification_channels: settings?.notification_channels ?? ['in_app'],
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
    (field: keyof FormData, value: string | boolean | AlertChannel[]) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      setHasChanges(true);
    },
    []
  );

  // Toggle notification channel
  const toggleChannel = useCallback((channel: AlertChannel) => {
    setFormData((prev) => {
      const channels = prev.notification_channels.includes(channel)
        ? prev.notification_channels.filter((c) => c !== channel)
        : [...prev.notification_channels, channel];
      return { ...prev, notification_channels: channels };
    });
    setHasChanges(true);
  }, []);

  // Handle save
  const handleSave = useCallback(async () => {
    try {
      await updateMutation.mutateAsync({
        auto_apply_enabled: formData.auto_apply_enabled,
        auto_apply_max_percent: formData.auto_apply_max_percent,
        require_approval_above: formData.require_approval_above,
        min_confidence_threshold: parseFloat(formData.min_confidence_threshold),
        default_cooldown_hours: parseInt(formData.default_cooldown_hours),
        notification_channels: formData.notification_channels,
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
          {[...Array(4)].map((_, i) => (
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
            Configure automatic pricing behavior and notifications
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
        {/* Auto-Apply Settings */}
        <Card padding="md">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Automatic Price Application
          </h2>

          <div className="space-y-6">
            {/* Auto-apply toggle */}
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">Enable Auto-Apply</p>
                <p className="text-sm text-gray-500">
                  Automatically apply low-risk price recommendations
                </p>
              </div>
              <button
                type="button"
                onClick={() => handleChange('auto_apply_enabled', !formData.auto_apply_enabled)}
                className={cn(
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                  formData.auto_apply_enabled ? 'bg-blue-600' : 'bg-gray-200'
                )}
              >
                <span
                  className={cn(
                    'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                    formData.auto_apply_enabled ? 'translate-x-6' : 'translate-x-1'
                  )}
                />
              </button>
            </div>

            {/* Max auto-apply percent */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Maximum Auto-Apply Change (%)
              </label>
              <p className="text-sm text-gray-500 mb-2">
                Only auto-apply if price change is below this threshold
              </p>
              <input
                type="number"
                value={formData.auto_apply_max_percent}
                onChange={(e) => handleChange('auto_apply_max_percent', e.target.value)}
                min="0"
                max="100"
                step="0.5"
                disabled={!formData.auto_apply_enabled}
                className={cn(
                  'w-full max-w-xs px-3 py-2 border border-gray-300 rounded-lg text-sm',
                  'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                  'disabled:bg-gray-100 disabled:text-gray-500'
                )}
              />
            </div>
          </div>
        </Card>

        {/* Approval Settings */}
        <Card padding="md">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Approval Thresholds
          </h2>

          <div className="space-y-6">
            {/* Require approval above */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Require Approval Above (%)
              </label>
              <p className="text-sm text-gray-500 mb-2">
                Price changes above this percentage require manual approval
              </p>
              <input
                type="number"
                value={formData.require_approval_above}
                onChange={(e) => handleChange('require_approval_above', e.target.value)}
                min="0"
                max="100"
                step="1"
                className="w-full max-w-xs px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Min confidence threshold */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Minimum Confidence Score
              </label>
              <p className="text-sm text-gray-500 mb-2">
                Only generate recommendations above this confidence level (0.0 - 1.0)
              </p>
              <input
                type="number"
                value={formData.min_confidence_threshold}
                onChange={(e) => handleChange('min_confidence_threshold', e.target.value)}
                min="0"
                max="1"
                step="0.05"
                className="w-full max-w-xs px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
        </Card>

        {/* Cooldown Settings */}
        <Card padding="md">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Cooldown Period
          </h2>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Default Cooldown (hours)
            </label>
            <p className="text-sm text-gray-500 mb-2">
              Minimum time between price changes for the same product
            </p>
            <input
              type="number"
              value={formData.default_cooldown_hours}
              onChange={(e) => handleChange('default_cooldown_hours', e.target.value)}
              min="1"
              max="720"
              step="1"
              className="w-full max-w-xs px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </Card>

        {/* Notification Channels */}
        <Card padding="md">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Notification Channels
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            Choose how you want to be notified about pricing recommendations
          </p>

          <div className="grid gap-3">
            {notificationChannelOptions.map((channel) => {
              const isSelected = formData.notification_channels.includes(channel.value);
              return (
                <button
                  key={channel.value}
                  type="button"
                  onClick={() => toggleChannel(channel.value)}
                  className={cn(
                    'flex items-center justify-between p-4 border rounded-lg text-left transition-colors',
                    isSelected
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  )}
                >
                  <div>
                    <p className="font-medium text-gray-900">{channel.label}</p>
                    <p className="text-sm text-gray-500">{channel.description}</p>
                  </div>
                  <div
                    className={cn(
                      'w-5 h-5 rounded border-2 flex items-center justify-center',
                      isSelected
                        ? 'bg-blue-600 border-blue-600'
                        : 'border-gray-300'
                    )}
                  >
                    {isSelected && (
                      <svg
                        className="w-3 h-3 text-white"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={3}
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </Card>
      </div>
    </div>
  );
}
