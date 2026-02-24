// frontend/components/features/intelligence/IEHealthBanner.tsx
'use client';

import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import {
  Activity,
  Brain,
  FlaskConical,
  Target,
  Layers,
  AlertTriangle,
} from 'lucide-react';
import type { IEHealthStatus } from '@/types/intelligence';

interface IEHealthBannerProps {
  health: IEHealthStatus;
  isLoading?: boolean;
}

const statusVariant: Record<string, 'success' | 'warning' | 'danger'> = {
  healthy: 'success',
  degraded: 'warning',
  unhealthy: 'danger',
};

const statusLabel: Record<string, string> = {
  healthy: 'All Systems Operational',
  degraded: 'Partial Degradation',
  unhealthy: 'Pipeline Unhealthy',
};

function ComponentDot({ healthy }: { healthy: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${
        healthy ? 'bg-green-500' : 'bg-red-500'
      }`}
    />
  );
}

export function IEHealthBanner({ health, isLoading }: IEHealthBannerProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="flex items-center gap-4">
          <div className="h-6 w-48 bg-gray-200 rounded animate-pulse" />
          <div className="h-6 w-24 bg-gray-200 rounded animate-pulse" />
        </div>
      </Card>
    );
  }

  const components = [
    { label: 'Scoring Engine', healthy: health.scoring_engine_healthy, icon: Brain },
    { label: 'Experiments', healthy: health.experiment_manager_healthy, icon: FlaskConical },
    { label: 'Calibrator', healthy: health.calibrator_healthy, icon: Target },
    { label: 'Context Injector', healthy: health.context_injector_healthy, icon: Layers },
  ];

  return (
    <Card>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        {/* Left: status + version */}
        <div className="flex items-center gap-3">
          <Activity className="w-5 h-5 text-gray-400" />
          <Badge variant={statusVariant[health.status] ?? 'danger'}>
            {statusLabel[health.status] ?? health.status}
          </Badge>
          <span className="text-xs text-gray-400 font-mono">
            {health.pipeline_version}
          </span>
        </div>

        {/* Center: component status dots */}
        <div className="flex items-center gap-4">
          {components.map((c) => (
            <div key={c.label} className="flex items-center gap-1.5 text-xs text-gray-600">
              <ComponentDot healthy={c.healthy} />
              <c.icon className="w-3.5 h-3.5" />
              <span className="hidden lg:inline">{c.label}</span>
            </div>
          ))}
        </div>

        {/* Right: experiment stats */}
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span>
            <span className="font-semibold text-gray-900">{health.active_experiments}</span> active
          </span>
          <span>
            <span className="font-semibold text-gray-900">{health.converged_categories}</span>
            /{health.total_categories} converged
          </span>
          {health.drift_alerts_active > 0 && (
            <span className="flex items-center gap-1 text-amber-600">
              <AlertTriangle className="w-3.5 h-3.5" />
              {health.drift_alerts_active} alerts
            </span>
          )}
        </div>
      </div>
    </Card>
  );
}


