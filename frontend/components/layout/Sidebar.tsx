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
  Plug,
  Sliders,
  ListChecks,
  Bell,
  BarChart3,
  Wallet, 
  Sparkles, 
  TrendingUp,
} from 'lucide-react';

// Navigation items - each page in the dashboard
const navItems = [
  { 
    label: 'Dashboard', 
    href: '/dashboard', 
    icon: LayoutDashboard 
  },
  { 
    label: 'Analytics', 
    href: '/analytics', 
    icon: BarChart3 
  },
  { 
    label: 'Products', 
    href: '/products', 
    icon: Package 
  },
  { 
    label: 'Integrations',  
    href: '/integrations', 
    icon: Plug 
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
    label: 'Alerts', 
    href: '/alerts', 
    icon: Bell 
  },
  {                          
    label: 'AI Support',
    href: '/support',
    icon: Sparkles
  },
  {                          
    label: 'Market Trends',
    href: '/trends',
    icon: TrendingUp
  },
];

// Pricing section items
const pricingItems = [
  { 
    label: 'Recommendations', 
    href: '/pricing', 
    icon: DollarSign 
  },
  { 
    label: 'Rules', 
    href: '/pricing/rules', 
    icon: Sliders 
  },
  { 
    label: 'Pricing Settings', 
    href: '/pricing/settings', 
    icon: ListChecks 
  },
  { 
    label: 'Payments (MNEE)', 
    href: '/payments', 
    icon: Wallet 
  },
];

// System items
const systemItems = [
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

  // Check if nav item is active
  const isActive = (href: string) => {
    if (href === '/pricing') {
      // Exact match for /pricing recommendations, not rules or settings
      return pathname === '/pricing' || pathname?.startsWith('/pricing/recommendations');
    }
    return pathname === href || pathname?.startsWith(`${href}/`);
  };

  // Render a nav item
  const renderNavItem = (item: { label: string; href: string; icon: typeof LayoutDashboard }) => {
    const active = isActive(item.href);
    
    return (
      <li key={item.href}>
        <Link
          href={item.href}
          className={cn(
            // Base styles
            'flex items-center gap-3 px-3 py-2.5 rounded-lg',
            'text-sm font-medium transition-colors duration-200',
            // Active vs inactive styles
            active
              ? 'bg-gray-700 text-white'
              : 'text-gray-300 hover:bg-gray-700 hover:text-white'
          )}
        >
          <item.icon className="w-5 h-5" />
          {item.label}
        </Link>
      </li>
    );
  };

  // Render a section header
  const renderSectionHeader = (title: string) => (
    <li className="pt-4 pb-2">
      <span className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
        {title}
      </span>
    </li>
  );

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-gray-800 text-gray-50">
      {/* Logo / Brand */}
      <div className="flex items-center gap-2 px-6 py-5 border-b border-gray-700">
        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
          <span className="text-white font-bold text-sm">AP</span>
        </div>
        <span className="font-semibold text-lg">Actual Price</span>
      </div>

      {/* Navigation Links */}
      <nav className="mt-6 px-3 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 100px)' }}>
        <ul className="space-y-1">
          {/* Main Navigation */}
          {navItems.map(renderNavItem)}

          {/* Pricing Section */}
          {renderSectionHeader('Pricing')}
          {pricingItems.map(renderNavItem)}

          {/* System Section */}
          {renderSectionHeader('System')}
          {systemItems.map(renderNavItem)}
        </ul>
      </nav>
    </aside>
  );
}

