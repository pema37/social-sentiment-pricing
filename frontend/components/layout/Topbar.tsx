// Topbar Component
// Top navigation bar with user info and actions

'use client';

import { useAuthStore } from '@/lib/stores/auth-store';
import { LogOut, User } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { NotificationBell } from '@/components/features/alerts';

export function Topbar() {
  const router = useRouter();
  const { user, logout } = useAuthStore();

  // Handle logout
  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8">
      {/* Left side - can add breadcrumbs or search later */}
      <div>
        {/* Placeholder for future content */}
      </div>

      {/* Right side - User info and logout */}
      <div className="flex items-center gap-4">
        {/* Notifications */}
        <NotificationBell />

        {/* User info */}
        <div className="flex items-center gap-3">
          {/* Avatar */}
          <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center">
            <User className="w-4 h-4 text-gray-600" />
          </div>
          
          {/* Name and email */}
          <div className="hidden sm:block">
            <p className="text-sm font-medium text-gray-900">
              {user?.full_name || 'User'}
            </p>
            <p className="text-xs text-gray-500">
              {user?.email || ''}
            </p>
          </div>
        </div>

        {/* Logout button */}
        <button
          onClick={handleLogout}
          className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          title="Logout"
        >
          <LogOut className="w-5 h-5" />
        </button>
      </div>
    </header>
  );
}


