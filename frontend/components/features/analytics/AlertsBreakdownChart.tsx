// Alerts breakdown charts
'use client';

import { useMemo } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts';
import { Card, CardTitle } from '@/components/ui';
import { useAlertAnalytics } from '@/lib/hooks/use-analytics';

interface AlertsBreakdownChartProps {
  days?: number;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#f59e0b',
  low: '#3b82f6',
};

const TYPE_COLORS = [
  '#3b82f6', // blue
  '#8b5cf6', // purple
  '#06b6d4', // cyan
  '#10b981', // green
  '#f59e0b', // amber
  '#ef4444', // red
];

const STATUS_COLORS: Record<string, string> = {
  pending: '#f59e0b',
  acknowledged: '#3b82f6',
  resolved: '#10b981',
};

export function AlertsBreakdownChart({ days = 30 }: AlertsBreakdownChartProps) {
  const { data, isLoading } = useAlertAnalytics(days);

  const severityData = useMemo(() => {
    if (!data?.by_severity) return [];
    return Object.entries(data.by_severity).map(([name, value]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      value,
      color: SEVERITY_COLORS[name] || '#9ca3af',
    }));
  }, [data]);

  const typeData = useMemo(() => {
    if (!data?.by_type) return [];
    return Object.entries(data.by_type).map(([name, value], index) => ({
      name: name.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
      value,
      color: TYPE_COLORS[index % TYPE_COLORS.length],
    }));
  }, [data]);

  const statusData = useMemo(() => {
    if (!data?.by_status) return [];
    return Object.entries(data.by_status).map(([name, value]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      value,
      color: STATUS_COLORS[name] || '#9ca3af',
    }));
  }, [data]);

  if (isLoading) {
    return (
      <Card>
        <CardTitle>Alert Analytics</CardTitle>
        <div className="h-64 mt-4 bg-gray-100 rounded animate-pulse" />
      </Card>
    );
  }

  const hasData = data && data.total_alerts_7d > 0;

  return (
    <Card>
      <div className="flex items-center justify-between">
        <div>
          <CardTitle>Alert Analytics</CardTitle>
          <p className="text-sm text-gray-500 mt-1">
            {data?.total_alerts_7d ?? 0} alerts in the last {days} days
          </p>
        </div>
      </div>

      {hasData ? (
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* By Severity - Pie Chart */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-3 text-center">By Severity</h4>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={severityData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={60}
                    innerRadius={30}
                    paddingAngle={2}
                  >
                    {severityData.map((entry, index) => (
                      <Cell key={`severity-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'white',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Legend
                    verticalAlign="bottom"
                    height={36}
                    formatter={(value) => <span className="text-xs text-gray-600">{value}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* By Status - Pie Chart */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-3 text-center">By Status</h4>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={60}
                    innerRadius={30}
                    paddingAngle={2}
                  >
                    {statusData.map((entry, index) => (
                      <Cell key={`status-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'white',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Legend
                    verticalAlign="bottom"
                    height={36}
                    formatter={(value) => <span className="text-xs text-gray-600">{value}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* By Type - Bar Chart */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-3 text-center">By Type</h4>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={typeData} layout="vertical" margin={{ left: 0, right: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 10 }} stroke="#9ca3af" />
                  <YAxis
                    type="category"
                    dataKey="name"
                    tick={{ fontSize: 10 }}
                    stroke="#9ca3af"
                    width={80}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'white',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                      fontSize: '12px',
                    }}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {typeData.map((entry, index) => (
                      <Cell key={`type-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      ) : (
        <div className="h-48 mt-4 flex items-center justify-center text-gray-500">
          <p className="text-sm">No alert data available</p>
        </div>
      )}
    </Card>
  );
}
