// Admin Page
'use client';

import { SectionHeader, Card, CardTitle } from '@/components/ui';

export default function AdminPage() {
  return (
    <div>
      <SectionHeader
        title="Admin"
        description="System administration and user management"
      />

      <div className="space-y-6">
        {/* User management */}
        <Card>
          <CardTitle>User Management</CardTitle>
          <div className="mt-4 text-gray-400">
            User management coming soon...
          </div>
        </Card>

        {/* System logs */}
        <Card>
          <CardTitle>System Logs</CardTitle>
          <div className="mt-4 text-gray-400">
            System logs coming soon...
          </div>
        </Card>
      </div>
    </div>
  );
}
