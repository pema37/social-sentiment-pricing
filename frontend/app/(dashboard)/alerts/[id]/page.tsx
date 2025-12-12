// Single alert detail page
'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { formatDistanceToNow, format } from 'date-fns';
import { ArrowLeft } from 'lucide-react';
import { useAlert, useAcknowledgeAlert, useResolveAlert } from '@/lib/hooks/use-alerts';
import { AlertBadge, AlertStatusBadge } from '@/components/features/alerts';

const alertTypeLabels: Record<string, string> = {
  sentiment_drop: 'Sentiment Drop',
  sentiment_spike: 'Sentiment Spike',
  price_recommendation: 'Price Recommendation',
  competitor_price_change: 'Competitor Price Change',
  volume_surge: 'Volume Surge',
  viral_mention: 'Viral Mention',
};

export default function AlertDetailPage() {
  const params = useParams();
  const alertId = params.id as string;

  const { data: alert, isLoading, error } = useAlert(alertId);
  const acknowledgeAlert = useAcknowledgeAlert();
  const resolveAlert = useResolveAlert();

  const handleAcknowledge = async () => {
    await acknowledgeAlert.mutateAsync(alertId);
  };

  const handleResolve = async () => {
    await resolveAlert.mutateAsync(alertId);
  };

  if (isLoading) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="animate-pulse">
          <div className="h-6 w-32 bg-gray-200 rounded mb-6" />
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="h-8 w-3/4 bg-gray-200 rounded mb-4" />
            <div className="h-4 w-full bg-gray-100 rounded mb-2" />
            <div className="h-4 w-2/3 bg-gray-100 rounded" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !alert) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <Link
          href="/alerts"
          className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Alerts
        </Link>
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
          <p className="text-red-600 font-medium">Failed to load alert</p>
          <p className="text-sm text-gray-500 mt-1">
            {error?.message || 'Alert not found'}
          </p>
        </div>
      </div>
    );
  }

  const isPending = alert.status === 'pending';
  const isAcknowledged = alert.status === 'acknowledged';

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Back link */}
      <Link
        href="/alerts"
        className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Alerts
      </Link>

      {/* Alert card */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-gray-100">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <AlertBadge severity={alert.severity} />
                <AlertStatusBadge status={alert.status} />
                <span className="text-sm text-gray-500">
                  {alertTypeLabels[alert.alert_type] || alert.alert_type}
                </span>
              </div>
              <h1 className="text-xl font-semibold text-gray-900">{alert.title}</h1>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 shrink-0">
              {isPending && (
                <button
                  onClick={handleAcknowledge}
                  disabled={acknowledgeAlert.isPending}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                >
                  {acknowledgeAlert.isPending ? 'Acknowledging...' : 'Acknowledge'}
                </button>
              )}
              {isAcknowledged && (
                <button
                  onClick={handleResolve}
                  disabled={resolveAlert.isPending}
                  className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50"
                >
                  {resolveAlert.isPending ? 'Resolving...' : 'Resolve'}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="p-6">
          <p className="text-gray-700 whitespace-pre-wrap">{alert.message}</p>
        </div>

        {/* Metadata */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-100">
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-gray-500">Created</dt>
              <dd className="text-gray-900 mt-0.5">
                {format(new Date(alert.created_at), 'PPp')}
                <span className="text-gray-500 ml-1">
                  ({formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })})
                </span>
              </dd>
            </div>

            {alert.acknowledged_at && (
              <div>
                <dt className="text-gray-500">Acknowledged</dt>
                <dd className="text-gray-900 mt-0.5">
                  {format(new Date(alert.acknowledged_at), 'PPp')}
                </dd>
              </div>
            )}

            {alert.resolved_at && (
              <div>
                <dt className="text-gray-500">Resolved</dt>
                <dd className="text-gray-900 mt-0.5">
                  {format(new Date(alert.resolved_at), 'PPp')}
                </dd>
              </div>
            )}

            {alert.product_id && (
              <div>
                <dt className="text-gray-500">Related Product</dt>
                <dd className="mt-0.5">
                  <Link
                    href={`/products/${alert.product_id}`}
                    className="text-blue-600 hover:underline"
                  >
                    View Product
                  </Link>
                </dd>
              </div>
            )}

            {alert.recommendation_id && (
              <div>
                <dt className="text-gray-500">Related Recommendation</dt>
                <dd className="mt-0.5">
                  <Link
                    href={`/pricing/recommendations/${alert.recommendation_id}`}
                    className="text-blue-600 hover:underline"
                  >
                    View Recommendation
                  </Link>
                </dd>
              </div>
            )}
          </dl>
        </div>
      </div>
    </div>
  );
}
