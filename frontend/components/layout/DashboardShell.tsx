// DashboardShell Component
// Wraps all dashboard pages with Sidebar + Topbar + content area

import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

interface DashboardShellProps {
  children: React.ReactNode;  // Page content goes here
}

export function DashboardShell({ children }: DashboardShellProps) {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar - fixed on the left */}
      <Sidebar />

      {/* Main content area - offset by sidebar width (240px = w-60) */}
      <div className="ml-60">
        {/* Topbar - at the top */}
        <Topbar />

        {/* Page content - with padding */}
        <main className="p-10">
          {children}
        </main>
      </div>
    </div>
  );
}

