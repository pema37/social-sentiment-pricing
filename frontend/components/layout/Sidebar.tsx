// Sidebar Component
// Main navigation for the dashboard - always visible on the left

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  Package,
  Users,
  MessageSquare,
  DollarSign,
  Settings,
  Key,
  Shield,
} from 'lucide-react';

// Navigation items - each page in the dashboard
const navItems = [
  { 
    label: 'Dashboard', 
    href: '/dashboard', 
    icon: LayoutDashboard 
  },
  { 
    label: 'Products', 
    href: '/products', 
    icon: Package 
  },
  { 
    label: 'Competitors', 
    href: '/competitors', 
    icon: Users 
  },
  { 
    label: 'Sentiment', 
    href: '/sentiment', 
    icon: MessageSquare 
  },
  { 
    label: 'Price Suggestions', 
    href: '/suggestions', 
    icon: DollarSign 
  },
  { 
    label: 'Settings', 
    href: '/settings', 
    icon: Settings 
  },
  { 
    label: 'API Keys', 
    href: '/api-keys', 
    icon: Key 
  },
  { 
    label: 'Admin', 
    href: '/admin', 
    icon: Shield 
  },
];

export function Sidebar() {
  // Get current path to highlight active nav item
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-gray-800 text-gray-50">
      {/* Logo / Brand */}
      <div className="flex items-center gap-2 px-6 py-5 border-b border-gray-700">
        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
          <span className="text-white font-bold text-sm">SSP</span>
        </div>
        <span className="font-semibold text-lg">Social Sentiment</span>
      </div>

      {/* Navigation Links */}
      <nav className="mt-6 px-3">
        <ul className="space-y-1">
          {navItems.map((item) => {
            // Check if this nav item is active
            const isActive = pathname === item.href || 
                            pathname?.startsWith(`${item.href}/`);
            
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    // Base styles
                    'flex items-center gap-3 px-3 py-2.5 rounded-lg',
                    'text-sm font-medium transition-colors duration-200',
                    // Active vs inactive styles
                    isActive
                      ? 'bg-gray-700 text-white'
                      : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                  )}
                >
                  <item.icon className="w-5 h-5" />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}

