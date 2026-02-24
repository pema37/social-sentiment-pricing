// frontend/components/features/intelligence/DriftAlertsList.tsx
'use client';

import { Card, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import {
  AlertTriangle,
  TrendingDown,
  Shuffle,
  BarChart3,
  ShieldAlert,
  CheckCircle,
} from 'lucide-react';
import type { DriftAlert } from '@/types/intelligence';

type DriftSeverity = DriftAlert['severity'];
type DriftType = DriftAlert['drift_type'];

interface DriftAlertsListProps {
  alerts: DriftAlert[];
  isLoading?: boolean;
}

const severityConfig: Record<DriftSeverity, { variant: 'info' | 'warning' | 'danger'; icon: typeof AlertTriangle }> = {
  info: { variant: 'info', icon: BarChart3 },
  warning: { variant: 'warning', icon: AlertTriangle },
  critical: { variant: 'danger', icon: ShieldAlert },
};

const driftTypeLabel: Record<DriftType, string> = {
  correlation_drop: 'Correlation Drop',
  distribution_shift: 'Distribution Shift',
  acceptance_change: 'Acceptance Change',
  lift_decline: 'Revenue Lift Decline',
};

const driftTypeIcon: Record<DriftType, typeof TrendingDown> = {
  correlation_drop: TrendingDown,
  distribution_shift: Shuffle,
  acceptance_change: BarChart3,
  lift_decline: TrendingDown,
};

function AlertRow({ alert }: { alert: DriftAlert }) {
  const config = severityConfig[alert.severity] ?? severityConfig.info;
  const TypeIcon = driftTypeIcon[alert.drift_type] ?? BarChart3;

  return (
    <div
      className={`flex items-start gap-3 p-3 rounded-lg border ${
        alert.severity === 'critical'
          ? 'bg-red-50 border-red-200'
          : alert.severity === 'warning'
          ? 'bg-amber-50 border-amber-200'
          : 'bg-blue-50 border-blue-200'
      }`}
    >
      <div className="pt-0.5">
        <config.icon className={`w-4 h-4 ${
          alert.severity === 'critical'
            ? 'text-red-600'
            : alert.severity === 'warning'
            ? 'text-amber-600'
            : 'text-blue-600'
        }`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <Badge variant={config.variant}>{alert.severity}</Badge>
          <Badge variant="default">
            <TypeIcon className="w-3 h-3 mr-1 inline" />
            {driftTypeLabel[alert.drift_type] ?? alert.drift_type}
          </Badge>
          <span className="text-xs text-gray-500">{alert.category_id}</span>
        </div>
        <p className="text-sm text-gray-800">{alert.message}</p>
        <div className="flex items-center gap-4 mt-1.5 text-xs text-gray-500">
          <span>
            {alert.metric_name}: <span className="font-medium">{alert.current_value.toFixed(3)}</span>
            {' '}(threshold: {alert.threshold.toFixed(3)})
          </span>
          <span>{new Date(alert.detected_at).toLocaleDateString()}</span>
          {alert.requires_action && (
            <span className="text-amber-600 font-medium">Action required</span>
          )}
        </div>
      </div>
    </div>
  );
}

export function DriftAlertsList({ alerts, isLoading }: DriftAlertsListProps) {
  if (isLoading) {
    return (
      <Card>
        <CardTitle>Drift Alerts</CardTitle>
        <div className="mt-4 space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-20 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      </Card>
    );
  }

  const critical = alerts.filter((a) => a.severity === 'critical');
  const warning = alerts.filter((a) => a.severity === 'warning');
  const info = alerts.filter((a) => a.severity === 'info');

  // Show critical first, then warning, then info
  const sorted = [...critical, ...warning, ...info];

  return (
    <Card>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-gray-400" />
          <CardTitle>Drift Alerts</CardTitle>
        </div>
        {alerts.length > 0 ? (
          <div className="flex gap-2">
            {critical.length > 0 && <Badge variant="danger">{critical.length} critical</Badge>}
            {warning.length > 0 && <Badge variant="warning">{warning.length} warning</Badge>}
            {info.length > 0 && <Badge variant="info">{info.length} info</Badge>}
          </div>
        ) : (
          <Badge variant="success">No alerts</Badge>
        )}
      </div>
      <p className="text-sm text-gray-500 mb-4">
        Model degradation signals — elasticity shifts, distribution changes, declining lift
      </p>

      {sorted.length === 0 ? (
        <div className="text-center py-8 text-sm text-gray-400">
          <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-300" />
          No active drift alerts. The pricing models are performing within expected bounds.
        </div>
      ) : (
        <div className="space-y-2">
          {sorted.map((alert) => (
            <AlertRow key={alert.alert_id} alert={alert} />
          ))}
        </div>
      )}
    </Card>
  );
}


