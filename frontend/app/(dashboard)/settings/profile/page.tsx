// Profile Settings Page
'use client';

import { useState } from 'react';
import { Card, CardTitle } from '@/components/ui';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { User, Mail, Calendar, Save } from 'lucide-react';
import { useAuthStore } from '@/lib/stores/auth-store';
import { useUpdateProfile } from '@/lib/hooks/use-user';

export default function ProfileSettingsPage() {
  const { user } = useAuthStore();
  const updateProfile = useUpdateProfile();

  const [fullName, setFullName] = useState(user?.full_name || '');
  const [email, setEmail] = useState(user?.email || '');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    const updates: { full_name?: string; email?: string } = {};
    
    if (fullName !== user?.full_name) {
      updates.full_name = fullName;
    }
    if (email !== user?.email) {
      updates.email = email;
    }

    if (Object.keys(updates).length > 0) {
      updateProfile.mutate(updates);
    }
  };

  const hasChanges = fullName !== user?.full_name || email !== user?.email;

  const formatDate = (dateString: string | undefined) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  return (
    <div className="space-y-6">
      {/* Profile Information */}
      <Card>
        <CardTitle>Profile Information</CardTitle>
        <p className="text-sm text-gray-500 mt-1">
          Update your personal information
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="fullName" className="block text-sm font-medium text-gray-700 mb-1">
              Full Name
            </label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                id="fullName"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="pl-10"
                placeholder="Enter your full name"
              />
            </div>
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              Email Address
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="pl-10"
                placeholder="Enter your email"
              />
            </div>
          </div>

          <div className="pt-4">
            <Button
              type="submit"
              disabled={!hasChanges || updateProfile.isPending}
            >
              <Save className="w-4 h-4 mr-2" />
              {updateProfile.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </form>
      </Card>

      {/* Account Information */}
      <Card>
        <CardTitle>Account Information</CardTitle>
        <p className="text-sm text-gray-500 mt-1">
          Your account details
        </p>

        <div className="mt-6 space-y-4">
          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gray-100 rounded-lg">
                <User className="w-4 h-4 text-gray-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">User ID</p>
                <p className="text-xs text-gray-500">Your unique identifier</p>
              </div>
            </div>
            <p className="text-sm text-gray-600 font-mono">
              {user?.id ? `${user.id.slice(0, 8)}...` : 'N/A'}
            </p>
          </div>

          <div className="flex items-center justify-between py-3 border-b border-gray-100">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gray-100 rounded-lg">
                <Calendar className="w-4 h-4 text-gray-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Member Since</p>
                <p className="text-xs text-gray-500">Account creation date</p>
              </div>
            </div>
            <p className="text-sm text-gray-600">
              {formatDate(user?.created_at)}
            </p>
          </div>

          <div className="flex items-center justify-between py-3">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${user?.is_active ? 'bg-green-100' : 'bg-red-100'}`}>
                <div className={`w-2 h-2 rounded-full ${user?.is_active ? 'bg-green-500' : 'bg-red-500'}`} />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Account Status</p>
                <p className="text-xs text-gray-500">Current account state</p>
              </div>
            </div>
            <span
              className={`text-sm px-2 py-1 rounded-full ${
                user?.is_active
                  ? 'bg-green-100 text-green-700'
                  : 'bg-red-100 text-red-700'
              }`}
            >
              {user?.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
        </div>
      </Card>
    </div>
  );
}
