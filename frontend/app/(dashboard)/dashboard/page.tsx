// Dashboard Page
// Main overview page with stats and charts

'use client';

import { Card, CardTitle, SectionHeader } from '@/components/ui';
import { Package, MessageSquare, DollarSign, Users } from 'lucide-react';

// Stat card component
function StatCard({ 
  title, 
  value, 
  change, 
  icon: Icon 
}: { 
  title: string; 
  value: string; 
  change: string; 
  icon: React.ElementType;
}) {
  const isPositive = change.startsWith('+');
  
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-semibold text-gray-900 mt-1">{value}</p>
          <p className={`text-sm mt-1 ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
            {change}
          </p>
        </div>
        <div className="p-2 bg-blue-50 rounded-lg">
          <Icon className="w-5 h-5 text-blue-600" />
        </div>
      </div>
    </Card>
  );
}

export default function DashboardPage() {
  return (
    <div>
      {/* Page header */}
      <SectionHeader
        title="Dashboard"
        description="Monitor your pricing and sentiment analytics"
      />

      {/* Stats grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          title="Products Tracked"
          value="24"
          change="+3 this month"
          icon={Package}
        />
        <StatCard
          title="Avg Sentiment"
          value="88%"
          change="+5% from last week"
          icon={MessageSquare}
        />
        <StatCard
          title="Pending Suggestions"
          value="12"
          change="Awaiting review"
          icon={DollarSign}
        />
        <StatCard
          title="Competitors"
          value="8"
          change="Actively monitoring"
          icon={Users}
        />
      </div>

      {/* Charts section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sentiment trend chart placeholder */}
        <Card>
          <CardTitle>Sentiment Trend (Last 7 Days)</CardTitle>
          <div className="h-64 flex items-center justify-center text-gray-400 mt-4">
            Chart coming soon...
          </div>
        </Card>

        {/* Revenue impact chart placeholder */}
        <Card>
          <CardTitle>Revenue Impact (Last 7 Months)</CardTitle>
          <div className="h-64 flex items-center justify-center text-gray-400 mt-4">
            Chart coming soon...
          </div>
        </Card>
      </div>
    </div>
  );
}
