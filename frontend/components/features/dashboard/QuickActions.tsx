// Quick actions widget for dashboard
'use client';

import Link from 'next/link';
import {
  Plus,
  Upload,
  Plug,
  Sliders,
  TrendingUp,
  Users,
} from 'lucide-react';

interface QuickAction {
  label: string;
  description: string;
  href: string;
  icon: React.ElementType;
  iconBgColor: string;
  iconColor: string;
}

const actions: QuickAction[] = [
  {
    label: 'Add Product',
    description: 'Create a new product to track',
    href: '/products/new',
    icon: Plus,
    iconBgColor: 'bg-blue-50',
    iconColor: 'text-blue-600',
  },
  {
    label: 'Import Products',
    description: 'Sync from Shopify or WooCommerce',
    href: '/integrations',
    icon: Upload,
    iconBgColor: 'bg-green-50',
    iconColor: 'text-green-600',
  },
  {
    label: 'Connect Store',
    description: 'Link your e-commerce platform',
    href: '/integrations',
    icon: Plug,
    iconBgColor: 'bg-purple-50',
    iconColor: 'text-purple-600',
  },
  {
    label: 'Create Pricing Rule',
    description: 'Set up automated price adjustments',
    href: '/pricing/rules/new',
    icon: Sliders,
    iconBgColor: 'bg-amber-50',
    iconColor: 'text-amber-600',
  },
  {
    label: 'View Recommendations',
    description: 'Review pending price changes',
    href: '/pricing',
    icon: TrendingUp,
    iconBgColor: 'bg-teal-50',
    iconColor: 'text-teal-600',
  },
  {
    label: 'Add Competitor',
    description: 'Track competitor pricing',
    href: '/competitors',
    icon: Users,
    iconBgColor: 'bg-rose-50',
    iconColor: 'text-rose-600',
  },
];

interface QuickActionsProps {
  maxItems?: number;
}

export function QuickActions({ maxItems = 6 }: QuickActionsProps) {
  const displayActions = actions.slice(0, maxItems);

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {displayActions.map((action) => (
        <Link
          key={action.href + action.label}
          href={action.href}
          className="flex items-start gap-3 p-3 rounded-lg border border-gray-200 hover:border-gray-300 hover:shadow-sm transition-all group"
        >
          <div className={`p-2 rounded-lg ${action.iconBgColor} shrink-0`}>
            <action.icon className={`w-4 h-4 ${action.iconColor}`} />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-900 group-hover:text-blue-600 transition-colors">
              {action.label}
            </p>
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">
              {action.description}
            </p>
          </div>
        </Link>
      ))}
    </div>
  );
}
