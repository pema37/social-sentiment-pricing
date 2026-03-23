// frontend/components/layout/Sidebar.tsx
// Main navigation for the dashboard - always visible on the left
// Updated Feb 21, 2026 — Shopify embedded context awareness
// Updated Mar 02, 2026 — Added Pricing Audit link

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useShopifyEmbedded } from '@/lib/context/shopify-embedded';
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
  LogOut,
  ShieldCheck,
  Camera,
  CreditCard,
  SearchX,
  ShieldAlert,
} from 'lucide-react';

// ─── Nav item type ───────────────────────────────────────────────────

interface NavItem {
  label: string;
  href: string;
  icon: typeof LayoutDashboard;
  /** If true, only show in standalone (non-Shopify) mode */
  standaloneOnly?: boolean;
  /** If true, only show in Shopify embedded mode */
  embeddedOnly?: boolean;
}

// ─── Navigation config ───────────────────────────────────────────────

const navItems: NavItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Analytics', href: '/analytics', icon: BarChart3 },
  { label: 'Pricing Audit', href: '/analytics/audit', icon: SearchX },
  { label: 'Products', href: '/products', icon: Package },
  { label: 'Integrations', href: '/integrations', icon: Plug },
  { label: 'Competitors', href: '/competitors', icon: Users },
  { label: 'Sentiment', href: '/sentiment', icon: MessageSquare },
  { label: 'Trust Scoring', href: '/sentiment/trust', icon: ShieldCheck },
  { label: 'Alerts', href: '/alerts', icon: Bell },
  { label: 'Crisis Detector', href: '/alerts/crisis', icon: ShieldAlert },
  { label: 'AI Support', href: '/support', icon: Sparkles },
  { label: 'Market Trends', href: '/trends', icon: TrendingUp },
];

const pricingItems: NavItem[] = [
  { label: 'Recommendations', href: '/pricing', icon: DollarSign },
  { label: 'Rules', href: '/pricing/rules', icon: Sliders },
  { label: 'Pricing Settings', href: '/pricing/settings', icon: ListChecks },
  { label: 'Visual Pricing', href: '/pricing/visual', icon: Camera },
  // Standalone: show MNEE payments
  { label: 'Payments (MNEE)', href: '/payments', icon: Wallet, standaloneOnly: true },
  // Embedded: show Shopify billing link instead
  { label: 'Billing', href: '/settings/billing', icon: CreditCard, embeddedOnly: true },
];

const systemItems: NavItem[] = [
  { label: 'Settings', href: '/settings', icon: Settings },
  { label: 'API Keys', href: '/api-keys', icon: Key },
  { label: 'Admin', href: '/admin', icon: Shield },
];

// ─── Component ───────────────────────────────────────────────────────

interface SidebarProps {
  onLogout?: () => void;
  onLinkClick?: () => void;
}

export function Sidebar({ onLogout, onLinkClick }: SidebarProps) {
  const pathname = usePathname();
  const { isEmbedded } = useShopifyEmbedded();

  const closeOnAnchorInteraction = (target: EventTarget | null) => {
    if (!(target instanceof HTMLElement)) return;
    if (target.closest('a[href]')) {
      onLinkClick?.();
    }
  };

  const handleNavClickCapture = (event: React.MouseEvent<HTMLElement>) => {
    closeOnAnchorInteraction(event.target);
  };

  const handleNavPointerDownCapture = (event: React.PointerEvent<HTMLElement>) => {
    closeOnAnchorInteraction(event.target);
  };

  const handleNavTouchStartCapture = (event: React.TouchEvent<HTMLElement>) => {
    closeOnAnchorInteraction(event.target);
  };

  // Filter items based on embedded context
  const filterItems = (items: NavItem[]): NavItem[] =>
    items.filter((item) => {
      if (item.standaloneOnly && isEmbedded) return false;
      if (item.embeddedOnly && !isEmbedded) return false;
      return true;
    });

  const isActive = (href: string) => {
    if (href === '/pricing') {
      return pathname === '/pricing' || pathname?.startsWith('/pricing/recommendations');
    }
    if (href === '/sentiment/trust') {
      return pathname === '/sentiment/trust';
    }
    if (href === '/sentiment') {
      return pathname === '/sentiment';
    }
    // Pricing Audit: exact match so it doesn't conflict with /analytics
    if (href === '/analytics/audit') {
      return pathname === '/analytics/audit';
    }
    if (href === '/analytics') {
      return pathname === '/analytics';
    }
    return pathname === href || pathname?.startsWith(`${href}/`);
  };

  const renderNavItem = (item: NavItem) => {
    const active = isActive(item.href);

    const handleNavItemClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
      // Same-route clicks won't trigger navigation, so close the mobile drawer explicitly.
      if (active) {
        event.preventDefault();
      }
      onLinkClick?.();
    };

    return (
      <li key={item.href}>
        <Link
          href={item.href}
          onClick={handleNavItemClick}
          className={cn(
            'flex items-center gap-3 px-3 py-2.5 rounded-lg',
            'text-sm font-medium transition-colors duration-200',
            active
              ? 'bg-blue-600 text-white shadow-md'
              : 'text-gray-400 hover:bg-gray-700 hover:text-white'
          )}
        >
          <item.icon className={cn('w-5 h-5', active && 'text-white')} />
          {item.label}
        </Link>
      </li>
    );
  };

  const renderSectionHeader = (title: string) => (
    <li className="pt-4 pb-2">
      <span className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
        {title}
      </span>
    </li>
  );

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-gray-800 text-gray-50 flex flex-col">
      {/* Logo / Brand */}
      <div className="flex items-center gap-2 px-6 py-5 border-b border-gray-700">
        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
          <span className="text-white font-bold text-sm">AP</span>
        </div>
        <span className="font-semibold text-lg">ActualPrice</span>
      </div>

      {/* Navigation Links - scrollable */}
      <nav
        className="flex-1 mt-6 px-3 overflow-y-auto"
        onClickCapture={handleNavClickCapture}
        onPointerDownCapture={handleNavPointerDownCapture}
        onTouchStartCapture={handleNavTouchStartCapture}
      >
        <ul className="space-y-1">
          {/* Main Navigation */}
          {filterItems(navItems).map(renderNavItem)}

          {/* Pricing Section */}
          {renderSectionHeader('Pricing')}
          {filterItems(pricingItems).map(renderNavItem)}

          {/* System Section */}
          {renderSectionHeader('System')}
          {filterItems(systemItems).map(renderNavItem)}
        </ul>
      </nav>

      {/* Logout Button — only in standalone mode
          Inside Shopify, merchants don't "sign out" of an embedded app */}
      {!isEmbedded && onLogout && (
        <div className="p-4 border-t border-gray-700">
          <button
            onClick={onLogout}
            className={cn(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg w-full',
              'text-sm font-medium transition-colors duration-200',
              'text-gray-300 hover:bg-red-600 hover:text-white'
            )}
          >
            <LogOut className="w-5 h-5" />
            Sign Out
          </button>
        </div>
      )}
    </aside>
  );
}



