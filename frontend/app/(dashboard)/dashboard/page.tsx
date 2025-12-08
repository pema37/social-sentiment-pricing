// Dashboard Page
// Main overview page with stats, charts, alerts, and activity feed

'use client';

import { useState } from 'react';
import { Card, CardTitle, SectionHeader } from '@/components/ui';
import { Button } from '@/components/ui/Button';
import {
  Package,
  MessageSquare,
  DollarSign,
  Users,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Bell,
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
} from 'lucide-react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

// =============================================================================
// MOCK DATA - Replace with API calls later
// =============================================================================

const sentimentChartData = [
  { date: 'Mon', score: 0.65, mentions: 120 },
  { date: 'Tue', score: 0.58, mentions: 145 },
  { date: 'Wed', score: 0.72, mentions: 189 },
  { date: 'Thu', score: 0.45, mentions: 234 },
  { date: 'Fri', score: 0.68, mentions: 198 },
  { date: 'Sat', score: 0.82, mentions: 267 },
  { date: 'Sun', score: 0.75, mentions: 312 },
];

const revenueChartData = [
  { month: 'Jun', revenue: 42000, baseline: 40000 },
  { month: 'Jul', revenue: 45000, baseline: 41000 },
  { month: 'Aug', revenue: 48000, baseline: 42000 },
  { month: 'Sep', revenue: 52000, baseline: 43000 },
  { month: 'Oct', revenue: 58000, baseline: 44000 },
  { month: 'Nov', revenue: 61000, baseline: 45000 },
  { month: 'Dec', revenue: 67000, baseline: 46000 },
];

const alerts = [
  {
    id: '1',
    type: 'critical' as const,
    title: 'Negative sentiment spike',
    description: '"Wireless Headphones" sentiment dropped 32%',
    time: '5 min ago',
  },
  {
    id: '2',
    type: 'warning' as const,
    title: 'Competitor price change',
    description: 'TechCorp lowered prices by 15%',
    time: '23 min ago',
  },
  {
    id: '3',
    type: 'success' as const,
    title: 'Price applied',
    description: 'Smart Watch updated to $299.99',
    time: '1 hour ago',
  },
];

const recentActivity = [
  { id: '1', action: 'Price updated', target: 'Wireless Earbuds Pro', time: '2 min ago', type: 'price' as const },
  { id: '2', action: 'Sentiment analyzed', target: '156 new mentions', time: '5 min ago', type: 'sentiment' as const },
  { id: '3', action: 'Competitor tracked', target: 'TechCorp pricing', time: '12 min ago', type: 'competitor' as const },
  { id: '4', action: 'Rule triggered', target: 'Holiday discount', time: '25 min ago', type: 'rule' as const },
];

// =============================================================================
// COMPONENTS
// =============================================================================

function StatCard({ 
  title, 
  value, 
  change,
  trend,
  icon: Icon 
}: { 
  title: string; 
  value: string; 
  change: string;
  trend?: 'up' | 'down' | 'neutral';
  icon: React.ElementType;
}) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-semibold text-gray-900 mt-1">{value}</p>
          <div className="flex items-center gap-1 mt-1">
            {trend === 'up' && <ArrowUpRight className="w-4 h-4 text-green-500" />}
            {trend === 'down' && <ArrowDownRight className="w-4 h-4 text-red-500" />}
            <p className={`text-sm ${
              trend === 'up' ? 'text-green-600' : 
              trend === 'down' ? 'text-red-600' : 'text-gray-500'
            }`}>
              {change}
            </p>
          </div>
        </div>
        <div className="p-3 bg-blue-50 rounded-xl">
          <Icon className="w-6 h-6 text-blue-600" />
        </div>
      </div>
    </Card>
  );
}

function AlertItem({ alert }: { alert: typeof alerts[0] }) {
  const styles = {
    critical: { bg: 'bg-red-50', border: 'border-red-200', icon: AlertTriangle, iconColor: 'text-red-500' },
    warning: { bg: 'bg-amber-50', border: 'border-amber-200', icon: Bell, iconColor: 'text-amber-500' },
    success: { bg: 'bg-green-50', border: 'border-green-200', icon: CheckCircle, iconColor: 'text-green-500' },
  };
  const style = styles[alert.type];
  const IconComponent = style.icon;

  return (
    <div className={`p-3 rounded-lg border ${style.bg} ${style.border}`}>
      <div className="flex items-start gap-3">
        <IconComponent className={`w-5 h-5 ${style.iconColor} mt-0.5`} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900">{alert.title}</p>
          <p className="text-sm text-gray-600 mt-0.5">{alert.description}</p>
          <p className="text-xs text-gray-400 mt-1">{alert.time}</p>
        </div>
      </div>
    </div>
  );
}

function ActivityItem({ activity }: { activity: typeof recentActivity[0] }) {
  const icons = {
    price: DollarSign,
    sentiment: MessageSquare,
    competitor: Users,
    rule: CheckCircle,
  };
  const colors = {
    price: 'bg-green-100 text-green-600',
    sentiment: 'bg-blue-100 text-blue-600',
    competitor: 'bg-purple-100 text-purple-600',
    rule: 'bg-amber-100 text-amber-600',
  };
  const Icon = icons[activity.type];

  return (
    <div className="flex items-center gap-3 py-3 border-b border-gray-100 last:border-0">
      <div className={`p-2 rounded-lg ${colors[activity.type]}`}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-900">
          <span className="font-medium">{activity.action}</span>
          {' · '}
          <span className="text-gray-600">{activity.target}</span>
        </p>
      </div>
      <p className="text-xs text-gray-400">{activity.time}</p>
    </div>
  );
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white p-3 rounded-lg shadow-lg border border-gray-200">
      <p className="text-sm font-medium text-gray-900 mb-1">{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} className="text-sm text-gray-600">
          {entry.name}: <span className="font-medium">{entry.value}</span>
        </p>
      ))}
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function DashboardPage() {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => setIsRefreshing(false), 1500);
  };

  return (
    <div>
      {/* Page header */}
      <SectionHeader
        title="Dashboard"
        description="Monitor your pricing and sentiment analytics"
        action={
          <Button variant="secondary" size="sm" onClick={handleRefresh} isLoading={isRefreshing}>
            <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        }
      />

      {/* Stats grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          title="Products Tracked"
          value="24"
          change="+3 this month"
          trend="up"
          icon={Package}
        />
        <StatCard
          title="Avg Sentiment"
          value="+0.72"
          change="+8.5% from last week"
          trend="up"
          icon={TrendingUp}
        />
        <StatCard
          title="Pending Suggestions"
          value="12"
          change="3 urgent"
          trend="neutral"
          icon={DollarSign}
        />
        <StatCard
          title="Competitors"
          value="8"
          change="+2 new this week"
          trend="up"
          icon={Users}
        />
      </div>

      {/* Charts section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Sentiment trend chart */}
        <Card>
          <CardTitle>Sentiment Trend (Last 7 Days)</CardTitle>
          <div className="mt-4">
            <ResponsiveContainer width="100%" height={256}>
              <AreaChart data={sentimentChartData}>
                <defs>
                  <linearGradient id="sentimentGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563EB" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#6B7280' }} axisLine={{ stroke: '#E5E7EB' }} />
                <YAxis tick={{ fontSize: 12, fill: '#6B7280' }} axisLine={{ stroke: '#E5E7EB' }} domain={[0, 1]} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="score" name="Sentiment" stroke="#2563EB" strokeWidth={2} fill="url(#sentimentGradient)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Revenue impact chart */}
        <Card>
          <CardTitle>Revenue Impact (Last 7 Months)</CardTitle>
          <div className="mt-4">
            <ResponsiveContainer width="100%" height={256}>
              <LineChart data={revenueChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#6B7280' }} axisLine={{ stroke: '#E5E7EB' }} />
                <YAxis tick={{ fontSize: 12, fill: '#6B7280' }} axisLine={{ stroke: '#E5E7EB' }} tickFormatter={(v) => `$${v/1000}k`} />
                <Tooltip content={<CustomTooltip />} />
                <Line type="monotone" dataKey="baseline" name="Baseline" stroke="#9CA3AF" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                <Line type="monotone" dataKey="revenue" name="With SSP" stroke="#10B981" strokeWidth={2} dot={{ fill: '#10B981', r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Alerts and Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Alerts */}
        <Card>
          <div className="flex items-center justify-between mb-4">
            <CardTitle>Recent Alerts</CardTitle>
            <Button variant="ghost" size="sm">View All</Button>
          </div>
          <div className="space-y-3">
            {alerts.map((alert) => (
              <AlertItem key={alert.id} alert={alert} />
            ))}
          </div>
        </Card>

        {/* Activity */}
        <Card>
          <div className="flex items-center justify-between mb-4">
            <CardTitle>Recent Activity</CardTitle>
            <Button variant="ghost" size="sm">View All</Button>
          </div>
          <div>
            {recentActivity.map((activity) => (
              <ActivityItem key={activity.id} activity={activity} />
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
