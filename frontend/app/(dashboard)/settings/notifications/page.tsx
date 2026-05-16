'use client';

// Notification Settings Page

import { useState, useEffect, useCallback } from 'react';
import { Card, CardTitle } from '@/components/ui';
import { Button } from '@/components/ui/Button';
import { Bell, Mail, MessageSquare, Zap, TrendingDown, Users, Save } from 'lucide-react';
import { toast } from '@/lib/hooks/use-toast';
import { useAlertConfigurations, useCreateAlertConfiguration, useUpdateAlertConfiguration } from '@/lib/hooks/use-alerts';
import type { AlertType, AlertChannel, AlertConfiguration } from '@/types';

interface NotificationSettingDef {
  id: string;
  alertType: AlertType;
  label: string;
  description: string;
  icon: React.ElementType;
  defaultEmail: boolean;
  defaultInApp: boolean;
}

const settingDefs: NotificationSettingDef[] = [
  {
    id: 'price_recommendations',
    alertType: 'price_recommendation',
    label: 'Price Recommendations',
    description: 'When new pricing recommendations are generated',
    icon: Zap,
    defaultEmail: true,
    defaultInApp: true,
  },
  {
    id: 'sentiment_alerts',
    alertType: 'sentiment_drop',
    label: 'Sentiment Alerts',
    description: 'Significant changes in product sentiment',
    icon: TrendingDown,
    defaultEmail: true,
    defaultInApp: true,
  },
  {
    id: 'competitor_changes',
    alertType: 'competitor_price_change',
    label: 'Competitor Price Changes',
    description: 'When competitors change their prices',
    icon: Users,
    defaultEmail: false,
    defaultInApp: true,
  },
  {
    id: 'viral_mentions',
    alertType: 'viral_mention',
    label: 'Viral Mentions',
    description: 'When your products are trending on social media',
    icon: MessageSquare,
    defaultEmail: true,
    defaultInApp: true,
  },
];

interface ToggleState {
  email: boolean;
  inApp: boolean;
}

function buildTogglesFromConfigs(configs: AlertConfiguration[]): Record<string, ToggleState> {
  const toggles: Record<string, ToggleState> = {};
  for (const def of settingDefs) {
    const config = configs.find((c) => c.alert_type === def.alertType);
    if (config) {
      toggles[def.id] = {
        email: config.channels.includes('email'),
        inApp: config.channels.includes('in_app'),
      };
    } else {
      toggles[def.id] = { email: def.defaultEmail, inApp: def.defaultInApp };
    }
  }
  return toggles;
}

export default function NotificationSettingsPage() {
  const { data: configs, isLoading } = useAlertConfigurations();
  const createConfig = useCreateAlertConfiguration();
  const updateConfig = useUpdateAlertConfiguration();

  const [toggles, setToggles] = useState<Record<string, ToggleState>>(() =>
    Object.fromEntries(settingDefs.map((d) => [d.id, { email: d.defaultEmail, inApp: d.defaultInApp }]))
  );
  const [isSaving, setIsSaving] = useState(false);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (configs && !initialized) {
      setToggles(buildTogglesFromConfigs(configs));
      setInitialized(true);
    }
  }, [configs, initialized]);

  const handleToggle = (id: string, channel: 'email' | 'inApp') => {
    setToggles((prev) => ({
      ...prev,
      [id]: { ...prev[id], [channel]: !prev[id][channel] },
    }));
  };

  const handleSave = useCallback(async () => {
    if (!configs) return;
    setIsSaving(true);

    try {
      const promises: Promise<unknown>[] = [];

      for (const def of settingDefs) {
        const toggle = toggles[def.id];
        const channels: AlertChannel[] = [];
        if (toggle.email) channels.push('email');
        if (toggle.inApp) channels.push('in_app');

        const existing = configs.find((c) => c.alert_type === def.alertType);

        if (existing) {
          promises.push(
            updateConfig.mutateAsync({ id: existing.id, data: { channels } })
          );
        } else {
          promises.push(
            createConfig.mutateAsync({
              name: def.label,
              alert_type: def.alertType,
              channels,
              is_active: true,
            })
          );
        }
      }

      await Promise.all(promises);
      toast.success({ title: 'Preferences saved', message: 'Your notification preferences have been updated' });
    } catch {
      toast.error({ title: 'Save failed', message: 'Could not save notification preferences. Please try again.' });
    } finally {
      setIsSaving(false);
    }
  }, [configs, toggles, createConfig, updateConfig]);

  return (
    <div className="space-y-6">
      {/* Notification Preferences */}
      <Card>
        <CardTitle>Notification Preferences</CardTitle>
        <p className="text-sm text-gray-500 mt-1">
          Choose how you want to be notified about important events
        </p>

        <div className="mt-6">
          {/* Header */}
          <div className="flex items-center justify-end gap-8 pb-3 border-b border-gray-200">
            <div className="flex items-center gap-1 text-sm font-medium text-gray-500">
              <Mail className="w-4 h-4" />
              <span>Email</span>
            </div>
            <div className="flex items-center gap-1 text-sm font-medium text-gray-500">
              <Bell className="w-4 h-4" />
              <span>In-App</span>
            </div>
          </div>

          {/* Settings List */}
          <div className="divide-y divide-gray-100">
            {settingDefs.map((def) => {
              const toggle = toggles[def.id];
              return (
                <div key={def.id} className="flex items-center justify-between py-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-gray-100 rounded-lg">
                      <def.icon className="w-4 h-4 text-gray-600" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">{def.label}</p>
                      <p className="text-xs text-gray-500">{def.description}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-8">
                    {/* Email Toggle */}
                    <button
                      type="button"
                      onClick={() => handleToggle(def.id, 'email')}
                      disabled={isLoading}
                      className={`relative w-10 h-6 rounded-full transition-colors ${
                        toggle?.email ? 'bg-blue-600' : 'bg-gray-200'
                      }`}
                    >
                      <span
                        className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${
                          toggle?.email ? 'translate-x-4' : 'translate-x-0'
                        }`}
                      />
                    </button>

                    {/* In-App Toggle */}
                    <button
                      type="button"
                      onClick={() => handleToggle(def.id, 'inApp')}
                      disabled={isLoading}
                      className={`relative w-10 h-6 rounded-full transition-colors ${
                        toggle?.inApp ? 'bg-blue-600' : 'bg-gray-200'
                      }`}
                    >
                      <span
                        className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${
                          toggle?.inApp ? 'translate-x-4' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="mt-6 pt-4 border-t border-gray-100">
          <Button onClick={handleSave} disabled={isSaving || isLoading}>
            <Save className="w-4 h-4 mr-2" />
            {isSaving ? 'Saving...' : 'Save Preferences'}
          </Button>
        </div>
      </Card>

      {/* Email Digest */}
      <DigestCard />
    </div>
  );
}

function DigestCard() {
  const [digestFrequency, setDigestFrequency] = useState('weekly');

  return (
    <Card>
      <CardTitle>Email Digest</CardTitle>
      <p className="text-sm text-gray-500 mt-1">
        Receive a summary of your activity
      </p>

      <div className="mt-6 space-y-3">
        <DigestOption
          label="Daily Digest"
          description="Get a daily summary every morning"
          value="daily"
          selected={digestFrequency === 'daily'}
          onSelect={setDigestFrequency}
        />
        <DigestOption
          label="Weekly Digest"
          description="Get a weekly summary every Monday"
          value="weekly"
          selected={digestFrequency === 'weekly'}
          onSelect={setDigestFrequency}
        />
        <DigestOption
          label="No Digest"
          description="Only receive real-time notifications"
          value="none"
          selected={digestFrequency === 'none'}
          onSelect={setDigestFrequency}
        />
      </div>
    </Card>
  );
}

function DigestOption({
  label,
  description,
  value,
  selected,
  onSelect,
}: {
  label: string;
  description: string;
  value: string;
  selected: boolean;
  onSelect: (value: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(value)}
      className={`w-full flex items-center justify-between p-3 rounded-lg border transition-colors ${
        selected
          ? 'border-blue-500 bg-blue-50'
          : 'border-gray-200 hover:border-gray-300'
      }`}
    >
      <div className="text-left">
        <p className={`text-sm font-medium ${selected ? 'text-blue-700' : 'text-gray-900'}`}>
          {label}
        </p>
        <p className={`text-xs ${selected ? 'text-blue-600' : 'text-gray-500'}`}>
          {description}
        </p>
      </div>
      <div
        className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
          selected ? 'border-blue-500 bg-blue-500' : 'border-gray-300'
        }`}
      >
        {selected && (
          <div className="w-2 h-2 bg-white rounded-full" />
        )}
      </div>
    </button>
  );
}
