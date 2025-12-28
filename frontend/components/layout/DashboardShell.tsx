// frontend/components/layout/DashboardShell.tsx
// DashboardShell Component
// Wraps all dashboard pages with Sidebar + Topbar + content area

'use client';

import { useState, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { Menu, X, User, LogOut } from 'lucide-react';
import { useAuthStore } from '@/lib/stores/auth-store';
import { NotificationBell } from '@/components/features/alerts';

interface DashboardShellProps {
  children: React.ReactNode;
}

export function DashboardShell({ children }: DashboardShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const { logout } = useAuthStore();

  // Close sidebar when route changes (user clicked a nav link)
  // This is a valid use case - disabling the eslint rule
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSidebarOpen(false);
  }, [pathname]);

  // Prevent body scroll when mobile menu is open
  useEffect(() => {
    if (sidebarOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [sidebarOpen]);

  // Handle logout
  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar - hidden on mobile, shown on lg+ */}
      <div className={`
        fixed inset-y-0 left-0 z-50 w-60 transform transition-transform duration-200 ease-in-out
        lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <Sidebar onLogout={handleLogout} />
      </div>

      {/* Mobile close button */}
      {sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(false)}
          className="fixed top-4 right-4 z-50 p-2 bg-white rounded-lg shadow-lg lg:hidden"
          aria-label="Close menu"
        >
          <X className="w-6 h-6" />
        </button>
      )}

      {/* Main content area */}
      <div className="lg:ml-60">
        {/* Mobile header - Shows hamburger + logo + alerts/profile/logout */}
        <div className="lg:hidden flex items-center justify-between p-4 bg-white border-b border-gray-200">
          {/* Left: Hamburger menu */}
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 rounded-lg hover:bg-gray-100"
            aria-label="Open menu"
            aria-expanded={sidebarOpen}
          >
            <Menu className="w-6 h-6" />
          </button>

          {/* Center: Logo */}
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-xs">AP</span>
            </div>
            <span className="font-semibold text-gray-900">ActualPrice</span>
          </div>

          {/* Right: Alerts, Profile, Logout - ALWAYS VISIBLE */}
          <div className="flex items-center gap-2">
            <NotificationBell />
            <button
              onClick={() => router.push('/settings/profile')}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
              title="Profile"
            >
              <User className="w-5 h-5" />
            </button>
            <button
              onClick={handleLogout}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
              title="Logout"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Desktop Topbar - hidden on mobile */}
        <div className="hidden lg:block">
          <Topbar />
        </div>

        {/* Page content */}
        <main className="p-4 lg:p-10">
          {children}
        </main>
      </div>
    </div>
  );
}
