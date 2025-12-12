// Notification Settings Page
'use client';

import { useState } from 'react';
import { Card, CardTitle } from '@/components/ui';
import { Button } from '@/components/ui/Button';
import { Bell, Mail, MessageSquare, Zap, TrendingDown, Users, Save } from 'lucide-react';
import { toast } from '@/lib/hooks/use-toast';

interface NotificationSetting {
  id: string;
  label: string;
  description: string;
  icon: React.ElementType;
  email: boolean;
  inApp: boolean;
}

const defaultSettings: NotificationSetting[] = [
  {
    id: 'price_recommendations',
    label: 'Price Recommendations',
    description: 'When new pricing recommendations are generated',
    icon: Zap,
    email: true,
    inApp: true,
  },
  {
    id: 'sentiment_alerts',
    label: 'Sentiment Alerts',
    description: 'Significant changes in product sentiment',
    icon: TrendingDown,
    email: true,
    inApp: true,
  },
  {
    id: 'competitor_changes',
    label: 'Competitor Price Changes',
    description: 'When competitors change their prices',
    icon: Users,
    email: false,
    inApp: true,
  },
  {
    id: 'viral_mentions',
    label: 'Viral Mentions',
    description: 'When your products are trending on social media',
    icon: MessageSquare,
    email: true,
    inApp: true,
  },
];

export default function NotificationSettingsPage() {
  const [settings, setSettings] = useState<NotificationSetting[]>(defaultSettings);
  const [isSaving, setIsSaving] = useState(false);

  const handleToggle = (id: string, channel: 'email' | 'inApp') => {
    setSettings((prev) =>
      prev.map((setting) =>
        setting.id === id
          ? { ...setting, [channel]: !setting[channel] }
          : setting
      )
    );
  };

  const handleSave = async () => {
    setIsSaving(true);
    
    // Simulate API call - replace with actual API when available
    await new Promise((resolve) => setTimeout(resolve, 1000));
    
    setIsSaving(false);
    toast.success({ title: 'Preferences saved', message: 'Your notification preferences have been updated' });
  };

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
            {settings.map((setting) => (
              <div key={setting.id} className="flex items-center justify-between py-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-gray-100 rounded-lg">
                    <setting.icon className="w-4 h-4 text-gray-600" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{setting.label}</p>
                    <p className="text-xs text-gray-500">{setting.description}</p>
                  </div>
                </div>

                <div className="flex items-center gap-8">
                  {/* Email Toggle */}
                  <button
                    type="button"
                    onClick={() => handleToggle(setting.id, 'email')}
                    className={`relative w-10 h-6 rounded-full transition-colors ${
                      setting.email ? 'bg-blue-600' : 'bg-gray-200'
                    }`}
                  >
                    <span
                      className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${
                        setting.email ? 'translate-x-4' : 'translate-x-0'
                      }`}
                    />
                  </button>

                  {/* In-App Toggle */}
                  <button
                    type="button"
                    onClick={() => handleToggle(setting.id, 'inApp')}
                    className={`relative w-10 h-6 rounded-full transition-colors ${
                      setting.inApp ? 'bg-blue-600' : 'bg-gray-200'
                    }`}
                  >
                    <span
                      className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${
                        setting.inApp ? 'translate-x-4' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 pt-4 border-t border-gray-100">
          <Button onClick={handleSave} disabled={isSaving}>
            <Save className="w-4 h-4 mr-2" />
            {isSaving ? 'Saving...' : 'Save Preferences'}
          </Button>
        </div>
      </Card>

      {/* Email Digest */}
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
          />
          <DigestOption
            label="Weekly Digest"
            description="Get a weekly summary every Monday"
            value="weekly"
          />
          <DigestOption
            label="No Digest"
            description="Only receive real-time notifications"
            value="none"
          />
        </div>
      </Card>
    </div>
  );
}

function DigestOption({
  label,
  description,
  value,
}: {
  label: string;
  description: string;
  value: string;
}) {
  const [selected, setSelected] = useState(value === 'weekly');

  return (
    <button
      type="button"
      onClick={() => setSelected(!selected)}
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
