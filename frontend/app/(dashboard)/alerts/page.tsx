// Alerts inbox page
'use client';

import { useState } from 'react';
import { useAlerts, useAlertStats, useAcknowledgeAllAlerts } from '@/lib/hooks/use-alerts';
import { AlertsList } from '@/components/features/alerts';
import type { AlertSeverity, AlertStatus } from '@/types';

export default function AlertsPage() {
  const [statusFilter, setStatusFilter] = useState<AlertStatus | ''>('');
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | ''>('');
  const [page, setPage] = useState(0);
  const limit = 20;

  const { data, isLoading, error } = useAlerts({
    skip: page * limit,
    limit,
    status: statusFilter || undefined,
    severity: severityFilter || undefined,
  });

  const { data: stats } = useAlertStats();
  const acknowledgeAll = useAcknowledgeAllAlerts();

  const handleAcknowledgeAll = () => {
    if (confirm('Acknowledge all pending alerts?')) {
      acknowledgeAll.mutate({
        severity: severityFilter || undefined,
      });
    }
  };

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Alerts</h1>
          <p className="text-gray-600 mt-1">
            {stats ? `${stats.total_unread} unread · ${stats.recent_24h} in last 24h` : 'Loading...'}
          </p>
        </div>

        <button
          onClick={handleAcknowledgeAll}
          disabled={acknowledgeAll.isPending || !stats?.total_unread}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {acknowledgeAll.isPending ? 'Acknowledging...' : 'Acknowledge All'}
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as AlertStatus | '');
            setPage(0);
          }}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option>
        </select>

        <select
          value={severityFilter}
          onChange={(e) => {
            setSeverityFilter(e.target.value as AlertSeverity | '');
            setPage(0);
          }}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Critical</p>
            <p className="text-2xl font-bold text-red-600">{stats.by_severity.critical || 0}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">High</p>
            <p className="text-2xl font-bold text-orange-600">{stats.by_severity.high || 0}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Medium</p>
            <p className="text-2xl font-bold text-yellow-600">{stats.by_severity.medium || 0}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Low</p>
            <p className="text-2xl font-bold text-slate-600">{stats.by_severity.low || 0}</p>
          </div>
        </div>
      )}

      {/* Alerts list */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <AlertsList
          alerts={data?.items ?? []}
          isLoading={isLoading}
          error={error as Error | null}
        />
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-600">
            Showing {page * limit + 1} to {Math.min((page + 1) * limit, data?.total ?? 0)} of {data?.total ?? 0}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= totalPages - 1}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
