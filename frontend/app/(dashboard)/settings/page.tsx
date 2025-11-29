// Settings Page
'use client';

import { SectionHeader, Card, CardTitle } from '@/components/ui';

export default function SettingsPage() {
  return (
    <div>
      <SectionHeader
        title="Settings"
        description="Manage your account and preferences"
      />

      <div className="space-y-6">
        {/* Profile settings */}
        <Card>
          <CardTitle>Profile</CardTitle>
          <div className="mt-4 text-gray-400">
            Profile settings coming soon...
          </div>
        </Card>

        {/* Notification settings */}
        <Card>
          <CardTitle>Notifications</CardTitle>
          <div className="mt-4 text-gray-400">
            Notification settings coming soon...
          </div>
        </Card>

        {/* Integration settings */}
        <Card>
          <CardTitle>Integrations</CardTitle>
          <div className="mt-4 text-gray-400">
            Integration settings coming soon...
          </div>
        </Card>
      </div>
    </div>
  );
}
