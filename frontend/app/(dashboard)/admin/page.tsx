// Admin Page
'use client';

import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/stores/auth-store';
import { SectionHeader, Card, CardTitle } from '@/components/ui';

export default function AdminPage() {
  const router = useRouter();
  const { user } = useAuthStore();

  if (!user?.is_superuser) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
        <h2 className="text-xl font-semibold text-gray-200 mb-2">Access Denied</h2>
        <p className="text-gray-400 mb-4">You do not have permission to access this page.</p>
        <button
          onClick={() => router.push('/dashboard')}
          className="text-blue-400 hover:text-blue-300 underline"
        >
          Return to Dashboard
        </button>
      </div>
    );
  }

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
